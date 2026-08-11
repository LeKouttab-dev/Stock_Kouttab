"""Auth-related Pydantic schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserOut


ROLE_LITERAL = Literal["Super Admin", "AdminBenevoles", "Compta", "Benevole"]


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    password_must_change: bool = False


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    """Corps optionnel : sans refresh token, toutes les sessions sont revoquees."""

    refresh_token: str | None = None


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SignupIn(BaseModel):
    """Public signup payload.

    Le role n'est volontairement PAS acceptable en entree : un demandeur
    pouvait sinon s'auto-attribuer ``Super Admin``, qu'un valideur pressé
    n'aurait pas forcement remarque en approuvant le compte. Tout compte cree
    ici est ``Benevole`` ; la promotion passe par ``PATCH /users/{id}/role``.
    """

    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=200)
    confirm_password: str | None = None
    nom: str | None = None
    prenom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None


class AdminSetupIn(BaseModel):
    email: EmailStr
    token: str
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=200)
    nom: str | None = None
    prenom: str | None = None


class InvitationValidateOut(BaseModel):
    valid: bool
    message: str
    email: EmailStr | None = None


class MessageOut(BaseModel):
    message: str
