"""User schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# "BenevoleFrais" : créé par le passage signé depuis gestion.lekouttab.fr,
# confiné aux notes de frais (voir tests/integration/test_perimetre_benevole_frais.py).
# "AdminStock" : l'« admin stock » de la buvette (09/10/2026). Voit et gere la
# buvette (produits, reappro, cloture de caisse) et recoit ses courriels (alertes
# de stock bas, recap du soir) ; aucun autre droit. Volontairement absent de
# `deps.ROLES_COMPLETS` : ni stock general, ni factures, ni contact.
ROLE_LITERAL = Literal[
    "Super Admin", "AdminBenevoles", "Compta", "Benevole", "BenevoleFrais", "AdminStock"
]
VALIDATION_LITERAL = Literal["pending", "active", "rejected"]


class UserBase(BaseModel):
    username: str
    role: ROLE_LITERAL
    nom: str | None = None
    prenom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None


class UserOut(UserBase):
    id: int
    validation_status: VALIDATION_LITERAL
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserDetailOut(UserOut):
    """Profil detaille. Le RIB n'y figure plus : il n'est pas conserve.

    Seules restent la date de sa derniere transmission au tresorier et la fin
    de l'IBAN — de quoi dire au benevole qu'il peut deposer une note de frais,
    et a la comptabilite quel beneficiaire payer.
    """

    rib_transmis_le: datetime | None = None
    rib_iban_fin: str | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=200)
    role: ROLE_LITERAL = "Benevole"
    nom: str | None = None
    prenom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None
    validation_status: VALIDATION_LITERAL = "active"


class UserUpdate(BaseModel):
    role: ROLE_LITERAL | None = None
    validation_status: VALIDATION_LITERAL | None = None


class UserValidate(BaseModel):
    validation_status: Literal["active", "rejected"]


class UserRoleUpdate(BaseModel):
    role: ROLE_LITERAL


class ProfileUpdate(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)
