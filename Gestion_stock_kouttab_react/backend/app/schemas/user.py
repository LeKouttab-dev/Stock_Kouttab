"""User schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


ROLE_LITERAL = Literal["Super Admin", "AdminBenevoles", "Compta", "Benevole"]
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
    """Includes RIB, restricted to Super Admin / Compta."""

    rib: str | None = None
    # Nom du document depose, et non son contenu : l'ecran a besoin de savoir
    # s'il y a une piece et laquelle, pas de recevoir les octets a chaque
    # affichage du profil. Le telechargement a son propre endpoint.
    rib_document_nom: str | None = None


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
    rib: str | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)
