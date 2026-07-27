"""Invitation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class InvitationIn(BaseModel):
    email: EmailStr


class InvitationOut(BaseModel):
    id: int
    email: EmailStr
    expires_at: datetime
    used: bool
    attempts: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationCreatedOut(InvitationOut):
    """Returned on creation; includes the plaintext token & URL once."""

    token: str
    invitation_url: str
