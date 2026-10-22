"""RIB : transmis par courriel au tresorier, plus jamais conserve.

Deux colonnes nullables sur `Admins` :

- `rib_transmis_le` : date du dernier RIB transmis. C'est elle, et non plus la
  presence d'un IBAN ou d'un document, qui ouvre le depot d'une note de frais.
- `rib_iban_fin` : les quatre derniers caracteres de l'IBAN, pour que la
  comptabilite retrouve le bon beneficiaire dans la banque.

Purement additive. Les anciennes colonnes (`rib`, `rib_document`...) restent :
le schema est partage avec la version legacy, qui casserait si elles
disparaissaient. Elles sont videes par `scripts/transmettre_et_purger_rib.py`,
et non ici — une migration n'envoie pas de courriels, et purger avant d'avoir
transmis ferait perdre les RIB des remboursements en attente.

Revision ID: f3a9b6c8d0e1
Revises: e2f8a3b5c7d9
Create Date: 2026-10-22 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f3a9b6c8d0e1"
down_revision = "e2f8a3b5c7d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("Admins", sa.Column("rib_transmis_le", sa.DateTime(), nullable=True))
    op.add_column("Admins", sa.Column("rib_iban_fin", sa.String(length=4), nullable=True))


def downgrade() -> None:
    op.drop_column("Admins", "rib_iban_fin")
    op.drop_column("Admins", "rib_transmis_le")
