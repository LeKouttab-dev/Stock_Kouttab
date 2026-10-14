"""Les reglages par agenda : salle habituelle et nom court.

La seule partie du calendrier qui touche la base. Tout le reste — evenements,
agendas — reste chez Google, par choix : dupliquer les evenements en creerait
une seconde source de verite, a tenir a jour.

Ce qui est stocke ici n'est pas une copie de Google, c'est **ce que Google ne
sait pas** : quelle salle occupe habituellement un cours qui n'en reserve
aucune, et comment abreger un nom d'agenda que la regle rate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.db.models import CalendrierAgendaReglage
from app.services.calendrier_salles import LONGUEUR_NOM_COURT, SALLES, ReglageAgenda


def reglages_par_agenda(db: Session) -> dict[str, ReglageAgenda]:
    """Tous les reglages, en **une** requete.

    La base est distante (cf. CLAUDE.md §14) : une requete par agenda ferait
    quarante-cinq allers-retours a chaque affichage du calendrier. La table
    compte au plus autant de lignes qu'il y a d'agendas, elle tient en memoire.
    """
    lignes = db.query(CalendrierAgendaReglage).all()
    return {
        ligne.agenda_id: ReglageAgenda(
            salle=ligne.salle,
            nom_court=ligne.nom_court,
            categorie=ligne.categorie,
            sous_categorie=ligne.sous_categorie,
        )
        for ligne in lignes
    }


def lignes_par_agenda(db: Session) -> dict[str, CalendrierAgendaReglage]:
    """Les lignes brutes, pour l'ecran de reglage (qui affiche aussi l'auteur)."""
    return {ligne.agenda_id: ligne for ligne in db.query(CalendrierAgendaReglage).all()}


LONGUEUR_CATEGORIE = 64


def _texte(valeur: str | None, longueur: int, libelle: str) -> str | None:
    texte = (valeur or "").strip()
    if len(texte) > longueur:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"{libelle} ne depasse pas {longueur} caracteres.",
        )
    # Vider un champ le rend a son calcul automatique, plutot que de figer une
    # chaine vide qui effacerait le libelle.
    return texte or None


def _valider(
    agenda_id: str, salle: str | None, nom_court: str | None
) -> tuple[str | None, str | None]:
    if not agenda_id or len(agenda_id) > 255:
        raise AppException(ErrorCode.VALIDATION_ERROR, detail="Identifiant d'agenda invalide.")
    if salle is not None and salle not in SALLES:
        # Une salle inconnue creerait une colonne fantome dans la grille.
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"Salle inconnue : {salle}. Attendu : {', '.join(SALLES)}.",
        )
    court = (nom_court or "").strip()
    if len(court) > LONGUEUR_NOM_COURT:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            detail=f"Le nom court ne depasse pas {LONGUEUR_NOM_COURT} caracteres.",
        )
    # Vider un champ le rend a son calcul automatique, plutot que de figer une
    # chaine vide qui effacerait le libelle de la carte.
    return salle, (court or None)


def enregistrer_reglages(
    db: Session,
    reglages: dict[str, dict[str, str | None]],
    auteur: str | None,
    noms_agendas: dict[str, str] | None = None,
) -> dict[str, ReglageAgenda]:
    """Ecrit les reglages recus et rend la table complete.

    **Tout ou rien** : la validation porte sur l'ensemble avant la moindre
    ecriture. Enregistrer la moitie d'un formulaire laisserait une grille a
    moitie rangee, sans dire laquelle.

    **Ce qui n'est pas envoye n'est pas touche.** L'ecran regle dix agendas sur
    quarante-cinq et enregistre ; un remplacement global effacerait les
    trente-cinq autres.

    Une ligne dont tous les champs sont vides est supprimee : elle
    ne dit plus rien, et la garder ferait croire a un reglage existant.
    """
    valides = {
        agenda_id: (
            *_valider(agenda_id, champs.get("salle"), champs.get("nom_court")),
            _texte(champs.get("categorie"), LONGUEUR_CATEGORIE, "La categorie"),
            _texte(champs.get("sous_categorie"), LONGUEUR_CATEGORIE, "La sous-categorie"),
        )
        for agenda_id, champs in reglages.items()
    }

    existantes = lignes_par_agenda(db)
    maintenant = datetime.utcnow()
    for agenda_id, (salle, court, categorie, sous_categorie) in valides.items():
        ligne = existantes.get(agenda_id)
        if salle is None and court is None and categorie is None and sous_categorie is None:
            if ligne is not None:
                db.delete(ligne)
            continue
        if ligne is None:
            ligne = CalendrierAgendaReglage(agenda_id=agenda_id)
            db.add(ligne)
        ligne.salle = salle
        ligne.nom_court = court
        ligne.categorie = categorie
        ligne.sous_categorie = sous_categorie
        ligne.agenda_nom = (noms_agendas or {}).get(agenda_id) or ligne.agenda_nom
        ligne.modifie_par = auteur
        ligne.modifie_le = maintenant

    db.commit()
    return reglages_par_agenda(db)


__all__ = ["enregistrer_reglages", "lignes_par_agenda", "reglages_par_agenda"]
