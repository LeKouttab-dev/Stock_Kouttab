"""Le compte systeme de la tablette de caisse (cf. `app.core.tablette`)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tablette import (
    EMAIL_TABLETTE,
    MOT_DE_PASSE_INUTILISABLE,
    NOM_TABLETTE,
    PRENOM_TABLETTE,
    ROLE_TABLETTE,
    USERNAME_TABLETTE,
)
from app.db.models import Admin


def get_compte_tablette(db: Session) -> Admin | None:
    return db.execute(
        select(Admin).where(Admin.username == USERNAME_TABLETTE)
    ).scalar_one_or_none()


def garantir_compte_tablette(db: Session) -> Admin:
    """Cree le compte s'il manque (meme contenu que la migration `f6a3b8c0d5e7`).

    Sert aux tests et a un poste de developpement monte par `create_all` ; en
    production, c'est la migration qui le cree.
    """
    compte = get_compte_tablette(db)
    if compte is not None:
        return compte
    compte = Admin(
        username=USERNAME_TABLETTE,
        password_hash=MOT_DE_PASSE_INUTILISABLE,
        role=ROLE_TABLETTE,
        validation_status="active",
        prenom=PRENOM_TABLETTE,
        nom=NOM_TABLETTE,
        email=EMAIL_TABLETTE,
    )
    db.add(compte)
    db.commit()
    db.refresh(compte)
    return compte
