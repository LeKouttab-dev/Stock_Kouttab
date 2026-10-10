"""Recap du soir de la buvette, envoye par courriel a 23 h (heure de Paris).

Greffe sur l'outbox-worker (`scripts/process_outbound_emails.py`), qui passe
toutes les dix minutes : il n'existe pas de planificateur, et un conteneur de
plus imposerait de recopier `compose.yml` a la main sur le VPS.

Une seule fois par jour : la date du dernier envoi est gardee dans
`BuvetteReglages` (`recap_dernier_envoi`). Elle n'est posee qu'APRES un envoi
reussi : un serveur SMTP en panne a 23 h laisse le passage suivant reessayer.

Destinataires : comptes AdminStock actifs et liste des reglages (cf.
`crud.buvette.destinataires_buvette`), comme les alertes de stock bas.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.crud import buvette as buvette_crud
from app.crud import buvette_cloture as cloture_crud
from app.crud.buvette_inventaire import dernier_comptage, utc_vers_paris
from app.db.models import BuvetteProduct, CaisseEtat
from app.services import email as email_service
from app.services import email_layout, liens


logger = get_logger("services.recap_buvette")

HEURE_DU_RECAP = 23

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _euros(centimes: int) -> str:
    signe = "-" if centimes < 0 else ""
    centimes = abs(centimes)
    return f"{signe}{centimes // 100},{centimes % 100:02d} €"


def _date_longue(jour: date) -> str:
    return f"{_JOURS[jour.weekday()]} {jour.day} {_MOIS[jour.month - 1]} {jour.year}"


def _duree(secondes: int) -> str:
    if secondes < 60:
        return "moins d'une minute"
    minutes = secondes // 60
    if minutes < 60:
        return f"{minutes} min"
    heures, minutes = divmod(minutes, 60)
    if heures < 48:
        return f"{heures} h {minutes:02d}"
    return f"{heures // 24} jours"


def donnees_du_jour(db: Session, jour: date) -> dict[str, Any]:
    """Tout ce que dit le recap, sans mise en forme (testable a part)."""
    resultat = buvette_crud.paiements(db, jour, jour)
    stats = buvette_crud.statistiques(db, jour, jour)
    sous_le_seuil = list(
        db.execute(
            select(BuvetteProduct)
            .where(
                BuvetteProduct.is_active.is_(True),
                BuvetteProduct.quantity < BuvetteProduct.seuil_alerte,
            )
            .order_by(BuvetteProduct.quantity.asc(), BuvetteProduct.name.asc())
        ).scalars()
    )
    etat = buvette_crud.get_etat(db)
    return {
        "jour": jour,
        "totaux": resultat["totaux"],
        "top": stats["par_produit"][:5],
        "sous_le_seuil": [(p.name, p.quantity, p.seuil_alerte) for p in sous_le_seuil],
        "clotures": cloture_crud.du_jour(db, jour),
        # Ce que la boite devrait contenir maintenant : ventes especes depuis le
        # dernier comptage (cloture ou inventaire). Sans aucun comptage, inconnu.
        "boite": cloture_crud.periode(db, None) if _a_un_comptage(db) else None,
        "etat": etat,
        "secondes_depuis": buvette_crud.secondes_depuis(etat.recu_at) if etat else None,
    }


def _a_un_comptage(db: Session) -> bool:
    return dernier_comptage(db) is not None


def _verdict(ecart: int) -> str:
    if ecart == 0:
        return "aucun écart"
    if ecart > 0:
        return f"excédent de {_euros(ecart)}"
    return f"manque de {_euros(-ecart)}"


def _heure(instant_utc: datetime) -> str:
    paris = utc_vers_paris(instant_utc)
    return f"{paris.hour} h {paris.minute:02d}"


def _horodatage(instant_utc: datetime) -> str:
    return f"{utc_vers_paris(instant_utc).strftime('%d/%m/%Y')} à {_heure(instant_utc)}"


def composer(donnees: dict[str, Any]) -> tuple[str, str]:
    """(sujet, corps) du recap. Texte simple, sans tiret cadratin."""
    jour: date = donnees["jour"]
    totaux = donnees["totaux"]
    sujet = f"Buvette : récapitulatif du {jour.strftime('%d/%m/%Y')}"

    lignes = [
        email_layout.entete(),
        "",
        f"Voici le récapitulatif de la buvette pour la journée du {_date_longue(jour)}.",
        "",
        "Chiffre d'affaires",
        f"- Total : {_euros(totaux['total_cents'])} ({totaux['nb_ventes']} vente(s))",
        f"- Carte (brut) : {_euros(totaux['carte_cents'])}",
        f"- Frais SumUp : {_euros(totaux.get('frais_carte_cents', 0))}",
        f"- Carte (net) : {_euros(totaux.get('carte_net_cents', totaux['carte_cents']))}",
        f"- Espèces : {_euros(totaux['especes_cents'])}",
        f"- HelloAsso : {_euros(totaux['helloasso_cents'])}",
        f"- Total net encaissé : "
        f"{_euros(totaux.get('net_total_cents', totaux['total_cents']))}",
        "",
        "Produits les plus vendus",
    ]
    if donnees["top"]:
        lignes += [
            f"- {p['nom']} : {p['quantite']} vendu(s), {_euros(p['ca_cents'])}"
            for p in donnees["top"]
        ]
    else:
        lignes.append("- Aucune vente aujourd'hui.")

    lignes += ["", "Produits sous le seuil d'alerte"]
    if donnees["sous_le_seuil"]:
        lignes += [
            f"- {nom} : il en reste {quantite} (seuil : {seuil})"
            for nom, quantite, seuil in donnees["sous_le_seuil"]
        ]
    else:
        lignes.append("- Aucun, le stock est suffisant.")

    lignes += ["", "Clôtures de la caisse espèces"]
    clotures = donnees["clotures"]
    boite = donnees["boite"]
    for cloture in clotures:
        lignes.append(
            f"- À {_heure(cloture.periode_fin)}, par "
            f"{cloture.saisi_par or 'un administrateur'} : attendu "
            f"{_euros(cloture.attendu_cents)}, compté {_euros(cloture.compte_cents)}, "
            f"{_verdict(cloture.ecart_cents)}."
        )
        if cloture.commentaire:
            lignes.append(f"  Commentaire : {cloture.commentaire}")
    if clotures:
        if boite is not None and boite["attendu_cents"]:
            lignes.append(
                "- Depuis la dernière clôture, espèces attendues dans la boîte : "
                f"{_euros(boite['attendu_cents'])}."
            )
    elif boite is not None:
        nature = "clôture" if boite["dernier"]["type"] == "cloture" else "inventaire"
        lignes.append(
            f"- Aucune clôture aujourd'hui. Dernier comptage le "
            f"{_horodatage(boite['debut'])} ({nature}) ; espèces attendues dans la "
            f"boîte : {_euros(boite['attendu_cents'])}."
        )
    else:
        lignes.append("- Aucun comptage des espèces enregistré pour l'instant.")

    lignes += ["", "Tablette de caisse"]
    etat = donnees["etat"]
    if etat is None:
        lignes.append("- Aucun signal reçu de la tablette pour l'instant.")
    else:
        details = [f"dernier contact il y a {_duree(donnees['secondes_depuis'])}"]
        if etat.batterie_pct is not None:
            charge = ", en charge" if etat.en_charge else ""
            details.append(f"batterie {etat.batterie_pct} %{charge}")
        if etat.version_name:
            details.append(f"version {etat.version_name}")
        if etat.ventes_en_attente:
            details.append(f"{etat.ventes_en_attente} vente(s) en attente d'envoi")
        if etat.ventes_rejetees:
            details.append(f"{etat.ventes_rejetees} vente(s) rejetée(s)")
        lignes.append("- " + ", ".join(details) + ".")
        lignes.append(f"- Compte SumUp : {libelle_sumup(etat)}.")
        lignes.append(f"- Lecteur de carte : {libelle_lecteur(etat)}.")

    lignes += [
        "",
        f"{liens.LIBELLE_ACCES} : {liens.lien_espace(None, 'buvette')}",
        "",
        email_layout.SIGNATURE,
    ]
    return sujet, "\n".join(lignes)


def libelle_sumup(etat: CaisseEtat) -> str:
    """Memes libelles que l'onglet Tablette ; booleen pour une ancienne app."""
    if etat.sumup_etat == "connecte":
        return "connecté"
    if etat.sumup_etat == "enregistre":
        return "connecté, se réveillera au prochain paiement"
    if etat.sumup_etat == "deconnecte":
        return "non connecté"
    return "connecté" if etat.sumup_connecte else "non connecté"


def libelle_lecteur(etat: CaisseEtat) -> str:
    """En veille n'est pas une panne : le lecteur se reveille au paiement."""
    if etat.lecteur_etat == "en_veille":
        return "en veille, se réveille au paiement"
    if etat.lecteur_etat == "non_appaire":
        return "non appairé"
    if etat.lecteur_etat == "connecte" or (etat.lecteur_etat is None and etat.lecteur_connecte):
        if etat.lecteur_batterie_pct is not None:
            return f"connecté (batterie {etat.lecteur_batterie_pct} %)"
        return "connecté"
    return "non connecté"


async def envoyer_recap(
    db: Session,
    jour: date | None = None,
    destinataires: Sequence[str] | None = None,
) -> list[str]:
    """Compose et envoie le recap de `jour` (aujourd'hui a Paris par defaut).

    `destinataires` force la liste, pour un essai a la main (« le recap a-t-il
    la bonne tete ? ») sans prevenir tout le monde. Rend la liste effective.
    Leve en cas d'echec d'envoi (`_send_raw`) : l'appelant decide de reessayer.
    """
    jour = jour or buvette_crud.aujourd_hui()
    liste = list(destinataires) if destinataires else buvette_crud.destinataires_buvette(db)
    if not liste:
        logger.warning("Recap buvette du %s : aucun destinataire, rien n'est envoye.", jour)
        return []
    sujet, corps = composer(donnees_du_jour(db, jour))
    await email_service._send_raw(sujet, corps, liste)
    logger.info("Recap buvette du %s envoye a %d destinataire(s).", jour, len(liste))
    return liste


async def envoyer_recap_si_l_heure(
    db: Session, maintenant: datetime | None = None
) -> bool:
    """A partir de 23 h (Paris), envoie le recap du jour s'il n'est pas deja parti.

    Rend vrai si un recap vient de partir. Appele a chaque passage du worker.
    """
    maintenant = maintenant or datetime.now(buvette_crud.PARIS)
    if maintenant.tzinfo is not None:
        maintenant = maintenant.astimezone(buvette_crud.PARIS)
    if maintenant.hour < HEURE_DU_RECAP:
        return False
    jour = maintenant.date()
    if buvette_crud.lire_reglage(db, buvette_crud.REGLAGE_DERNIER_RECAP) == jour.isoformat():
        return False
    envoyes = await envoyer_recap(db, jour)
    if not envoyes:
        return False
    buvette_crud.ecrire_reglage(db, buvette_crud.REGLAGE_DERNIER_RECAP, jour.isoformat())
    return True
