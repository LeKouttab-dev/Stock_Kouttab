"""Schemas de la file d'envois comptables."""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class OutboundEmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    entity_type: str
    entity_id: int
    subject: str
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None = None
    next_retry_at: datetime | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None

    # Stockes en JSON en base ; exposes en listes exploitables cote interface.
    recipients: str
    attachments: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recipient_list(self) -> list[str]:
        try:
            return json.loads(self.recipients or "[]")
        except ValueError:
            return []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def attachment_names(self) -> list[str]:
        """Noms de fichiers seuls : les chemins absolus revelent l'arborescence."""
        try:
            paths = json.loads(self.attachments or "[]")
        except ValueError:
            return []
        return [p.replace("\\", "/").rsplit("/", 1)[-1] for p in paths]


class EtatEnvoisOut(BaseModel):
    """Sante du circuit d'envoi, avant meme qu'un courriel ne soit tente.

    Une file vide et un serveur d'envoi coupe se ressemblent : sans ce signal,
    il faut deposer une piece pour decouvrir que rien ne part. C'est exactement
    ce qui a laisse la production muette pendant trois semaines.
    """

    email_enabled: bool
    smtp_configure: bool
    destinataires_compta: list[str]
    en_attente: int
    en_echec: int
