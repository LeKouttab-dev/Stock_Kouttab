"""Table des jetons de reinitialisation de mot de passe.

Sans elle, un oubli de mot de passe imposait une intervention manuelle en base :
c'est ce qui est arrive au compte Super Admin de production le 2026-08-11.

Revision ID: 9b7d0e5f1a06
Revises: 8a6c9d4e0f05
Create Date: 2026-08-12 01:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "9b7d0e5f1a06"
down_revision = "8a6c9d4e0f05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "PasswordResets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        # Seul le SHA256 du jeton est conserve : une fuite de la base ne permet
        # pas de fabriquer un lien valide.
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("requested_ip", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["id_user"], ["Admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_reset_token", "PasswordResets", ["token_hash"])
    op.create_index("idx_reset_user", "PasswordResets", ["id_user"])
    op.create_index("idx_reset_expires", "PasswordResets", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_reset_expires", table_name="PasswordResets")
    op.drop_index("idx_reset_user", table_name="PasswordResets")
    op.drop_index("idx_reset_token", table_name="PasswordResets")
    op.drop_table("PasswordResets")
