"""Le RIB doit etre illisible dans la base, pas seulement dans l'application.

Les tests de `test_crypto.py` verifient la primitive. Ceux-ci verifient ce qui
compte vraiment : ce qu'un `SELECT rib FROM Admins` rend a qui met la main sur
la base — export, sauvegarde egaree, acces MySQL direct.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import crypto
from app.crud import user as user_crud
from app.db.models import Admin


RIB = "FR76 3000 6000 0112 3456 7890 189"


def _rib_brut(db: Session, user_id: int) -> str | None:
    """Lit la colonne SANS passer par l'ORM, donc sans dechiffrement."""
    return db.execute(
        text("SELECT rib FROM Admins WHERE id = :id"), {"id": user_id}
    ).scalar()


def test_le_rib_est_chiffre_dans_la_colonne(db_session: Session, benevole_user: Admin):
    user_crud.update_profile(db_session, benevole_user.id, rib=RIB)

    brut = _rib_brut(db_session, benevole_user.id)
    assert brut is not None
    assert RIB not in brut
    assert crypto.est_chiffre(brut)


def test_le_rib_revient_en_clair_par_l_orm(db_session: Session, benevole_user: Admin):
    """Le chiffrement ne doit rien changer au code appelant : la comptabilite
    a besoin du RIB lisible pour rembourser."""
    user_crud.update_profile(db_session, benevole_user.id, rib=RIB)
    db_session.expire_all()

    relu = db_session.get(Admin, benevole_user.id)
    assert relu is not None
    assert relu.rib == RIB


def test_un_rib_en_clair_herite_reste_lisible(db_session: Session, benevole_user: Admin):
    """La base de production contient des RIB en clair au moment du
    deploiement : ils doivent continuer d'apparaitre, sans quoi la page des
    notes de frais se vide le jour de la mise en production."""
    db_session.execute(
        text("UPDATE Admins SET rib = :rib WHERE id = :id"),
        {"rib": RIB, "id": benevole_user.id},
    )
    db_session.commit()
    db_session.expire_all()

    relu = db_session.get(Admin, benevole_user.id)
    assert relu is not None
    assert relu.rib == RIB


def test_modifier_un_rib_herite_le_chiffre(db_session: Session, benevole_user: Admin):
    """Une modification effective chiffre la nouvelle valeur."""
    db_session.execute(
        text("UPDATE Admins SET rib = :rib WHERE id = :id"),
        {"rib": RIB, "id": benevole_user.id},
    )
    db_session.commit()
    db_session.expire_all()

    user_crud.update_profile(db_session, benevole_user.id, rib="FR76 1234 5678 9012 3456 7890 123")

    assert crypto.est_chiffre(_rib_brut(db_session, benevole_user.id) or "")


def test_reecrire_le_meme_rib_ne_convertit_pas_l_existant(
    db_session: Session, benevole_user: Admin
):
    """Limite assumee, et raison d'etre de la migration.

    L'ORM compare la valeur DECHIFFREE a celle qu'on lui donne : identiques, il
    n'emet aucun UPDATE, et le clair reste en base. Compter sur les
    enregistrements du profil pour convertir l'existant laisserait donc en clair
    le RIB de tous ceux qui ne le retouchent jamais — c'est la migration
    Alembic `2026_08_12_1200` qui s'en charge, une fois pour toutes.
    """
    db_session.execute(
        text("UPDATE Admins SET rib = :rib WHERE id = :id"),
        {"rib": RIB, "id": benevole_user.id},
    )
    db_session.commit()
    db_session.expire_all()

    user_crud.update_profile(db_session, benevole_user.id, rib=RIB)

    assert _rib_brut(db_session, benevole_user.id) == RIB


def test_un_rib_abime_ne_fait_pas_tomber_la_lecture(
    db_session: Session, benevole_user: Admin
):
    """Un seul compte abime ne doit pas rendre toute la page inaccessible aux
    autres : le RIB manque, le reste du profil s'affiche."""
    db_session.execute(
        text("UPDATE Admins SET rib = :rib WHERE id = :id"),
        {"rib": crypto.PREFIXE + "n_est_pas_du_base64_valide", "id": benevole_user.id},
    )
    db_session.commit()
    db_session.expire_all()

    relu = db_session.get(Admin, benevole_user.id)
    assert relu is not None
    assert relu.rib is None
    assert relu.username == benevole_user.username
