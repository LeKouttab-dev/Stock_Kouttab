"""Relance ponctuelle des benevoles : RIB manquant, commentaire non lu.

A lancer a la main, depuis le VPS :

    cd /opt/projets/kouttab-stock
    sudo docker compose exec api python scripts/relancer_benevoles.py --rib

**Rien ne part sans `--envoyer`.** Sans ce drapeau, le script se contente
d'afficher qui recevrait quoi. Ecrire a de vraies personnes ne se declenche pas
par inadvertance, et une liste de destinataires se relit avant, pas apres.

Deux relances, cumulables :

``--rib``
    Aux benevoles dont l'espace ne porte **aucun** releve d'identite bancaire :
    ni IBAN saisi, ni document depose. Sans RIB, la comptabilite ne peut pas
    virer, et la note reste approuvee sans jamais etre payee.

``--commentaires``
    A ceux dont une note porte un commentaire de la comptabilite qu'ils n'ont
    pas encore ouvert. Jusqu'au 2026-08-13, ce commentaire n'allumait aucune
    pastille et le courriel de l'epoque partait en « best-effort » : beaucoup
    n'ont jamais su qu'on leur demandait une correction.

``--utilisateur`` restreint a des comptes nommes (identifiant ou adresse,
repetable). Sans lui, la regle s'applique a tous ceux qu'elle designe.

Les envois passent par la **file** : ils apparaissent dans Administration >
Envois comptables, se relancent d'un clic, et ne se perdent pas si le serveur de
messagerie est indisponible.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.logger import get_logger  # noqa: E402
from app.db.models import Admin, Expense  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import outbox  # noqa: E402
from app.services.email_layout import composer  # noqa: E402


logger = get_logger("relance")

KIND_RIB = "relance_rib"
KIND_COMMENTAIRE = "relance_commentaire"


def _comptes_actifs(db: Session, noms: list[str]) -> list[Admin]:
    """Comptes vises, actifs et pourvus d'une adresse.

    Un compte sans courriel n'est pas relancable ; un compte en attente de
    validation n'a pas encore de raison de l'etre.
    """
    stmt = select(Admin).where(
        Admin.validation_status == "active", Admin.email.is_not(None)
    )
    comptes = list(db.execute(stmt).scalars().all())
    if not noms:
        return comptes

    recherches = {n.strip().lower() for n in noms if n.strip()}
    retenus = [
        compte
        for compte in comptes
        if compte.username.lower() in recherches
        or (compte.email or "").lower() in recherches
    ]
    introuvables = recherches - {c.username.lower() for c in retenus} - {
        (c.email or "").lower() for c in retenus
    }
    if introuvables:
        # Signale plutot que d'ignorer : une faute de frappe ne doit pas se
        # traduire par « personne a relancer », qu'on lirait comme un succes.
        logger.warning("Aucun compte actif pour : %s", ", ".join(sorted(introuvables)))
    return retenus


def _sans_rib(compte: Admin) -> bool:
    return not (compte.rib or "").strip() and not compte.rib_document_nom


def relancer_rib(db: Session, comptes: list[Admin], *, envoyer: bool) -> int:
    vises = [c for c in comptes if _sans_rib(c)]
    for compte in vises:
        corps = composer(
            prenom=compte.prenom,
            introduction=(
                "Votre espace ne comporte pas encore de releve d'identite bancaire. "
                "Sans lui, la comptabilite ne peut pas vous rembourser, meme une "
                "note deja approuvee."
            ),
            blocs=[("Compte", compte.full_name or compte.username)],
            conclusion=(
                "Rendez-vous dans « Notes de frais » puis l'onglet « Profil » : "
                "renseignez votre IBAN et deposez le document de votre banque "
                "(PDF ou photo). Il n'est visible que par vous et la comptabilite."
            ),
        )
        print(f"  RIB manquant  → {compte.username} <{compte.email}>")
        if envoyer:
            outbox.enqueue(
                db,
                kind=KIND_RIB,
                entity_type="user",
                entity_id=compte.id,
                recipients=[compte.email],
                subject="Votre relevé d'identité bancaire est attendu",
                body=corps,
            )
    return len(vises)


def relancer_commentaires(db: Session, comptes: list[Admin], *, envoyer: bool) -> int:
    """Une relance par personne, listant toutes ses notes commentees.

    Un courriel par note noierait le message chez qui en a plusieurs, et c'est
    precisement celui-la qu'il faut atteindre.
    """
    par_compte = {c.id: c for c in comptes}
    if not par_compte:
        return 0

    stmt = (
        select(Expense)
        .where(
            Expense.id_user.in_(par_compte),
            Expense.non_lu_demandeur.is_(True),
            Expense.commentaires_compta.is_not(None),
            Expense.commentaires_compta != "",
            Expense.archived_at.is_(None),
        )
        .order_by(Expense.id_user, Expense.date_depense)
    )

    notes_par_compte: dict[int, list[Expense]] = {}
    for note in db.execute(stmt).scalars().all():
        notes_par_compte.setdefault(note.id_user, []).append(note)

    for id_user, notes in notes_par_compte.items():
        compte = par_compte[id_user]
        detail = "\n".join(
            f"- {n.date_depense:%d/%m/%Y} — {n.fournisseur or 'sans fournisseur'} "
            f"({n.montant:.2f} EUR) : {n.commentaires_compta}"
            for n in notes
        )
        corps = composer(
            prenom=compte.prenom,
            introduction=(
                "La comptabilite a laisse un message sur "
                f"{'une de vos notes de frais' if len(notes) == 1 else 'plusieurs de vos notes de frais'} :"
                f"\n\n{detail}"
            ),
            conclusion=(
                "Retrouvez-les dans « Notes de frais », onglet « Mes demandes ». "
                "Repondez depuis l'espace « Nous contacter » si un point reste "
                "obscur."
            ),
        )
        print(f"  {len(notes)} commentaire(s) → {compte.username} <{compte.email}>")
        if envoyer:
            outbox.enqueue(
                db,
                kind=KIND_COMMENTAIRE,
                entity_type="user",
                entity_id=compte.id,
                recipients=[compte.email],
                subject="Un message de la comptabilité sur vos notes de frais",
                body=corps,
            )
    return len(notes_par_compte)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rib", action="store_true", help="Relancer les RIB manquants")
    parser.add_argument(
        "--commentaires", action="store_true", help="Relancer les commentaires non lus"
    )
    parser.add_argument(
        "--utilisateur",
        action="append",
        default=[],
        metavar="IDENTIFIANT",
        help="Restreindre a ce compte (identifiant ou adresse). Repetable.",
    )
    parser.add_argument(
        "--envoyer",
        action="store_true",
        help="Mettre reellement les courriels en file. Sans ce drapeau : simulation.",
    )
    args = parser.parse_args()

    if not (args.rib or args.commentaires):
        parser.error("Choisir au moins --rib ou --commentaires.")

    db = SessionLocal()
    try:
        comptes = _comptes_actifs(db, args.utilisateur)
        if not comptes:
            print("Aucun compte ne correspond.")
            return 0

        mode = "ENVOI" if args.envoyer else "SIMULATION (rien ne part)"
        print(f"\n=== {mode} — {len(comptes)} compte(s) examine(s) ===\n")

        total = 0
        if args.rib:
            print("Relance « RIB manquant » :")
            n = relancer_rib(db, comptes, envoyer=args.envoyer)
            print(f"  → {n} destinataire(s)\n")
            total += n
        if args.commentaires:
            print("Relance « commentaire non lu » :")
            n = relancer_commentaires(db, comptes, envoyer=args.envoyer)
            print(f"  → {n} destinataire(s)\n")
            total += n

        if args.envoyer:
            print(f"{total} courriel(s) en file. Suivi : Administration > Envois comptables.")
        else:
            print("Simulation terminee. Relancer avec --envoyer pour expedier.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
