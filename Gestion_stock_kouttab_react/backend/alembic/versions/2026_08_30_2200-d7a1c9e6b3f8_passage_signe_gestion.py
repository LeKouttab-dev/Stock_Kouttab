"""Passage signe depuis gestion.lekouttab.fr : jetons consommes.

La table ``SsoEchanges`` tient l'anti-rejeu du SSO entrant : chaque jeton de
passage porte un ``jti``, et son SHA256 est **insere** ici a l'echange. La
contrainte unique fait de l'insertion le verrou — atomique, partagee entre
workers, survivant aux redemarrages, la ou un set en memoire de process ne
tiendrait aucune de ces trois promesses.

Meme patron que ``RefreshTokens`` : seul le hash est stocke, une fuite de la
base ne permet de rejouer aucun jeton. Les lignes expirees sont purgees au fil
des echanges, la table reste minuscule.

Revision ID: d7a1c9e6b3f8
Revises: c5e9a7d4f1b6
Create Date: 2026-08-30 22:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d7a1c9e6b3f8"
down_revision = "c5e9a7d4f1b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "SsoEchanges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("jti_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_sso_expires", "SsoEchanges", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_sso_expires", table_name="SsoEchanges")
    op.drop_table("SsoEchanges")
