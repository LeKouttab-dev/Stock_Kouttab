"""Auth security tables and validation traceability.

Cree ``LoginAttempts`` (lockout persistant) et ``RefreshTokens`` (rotation et
revocation), et ajoute ``validated_by`` / ``validated_at`` sur ``Factures`` et
``NotesDeFrais``.

ATTENTION : ne jamais regenerer ce fichier avec ``alembic revision
--autogenerate``. L'historique Alembic ne connait que les tables buvette : un
autogenerate voudrait CREER les dix tables historiques et detruirait la
production. Les revisions de ce projet s'ecrivent a la main.

Revision ID: 5e4a7b2c8d03
Revises: 3c9d1e2f4a02
Create Date: 2026-07-27 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "5e4a7b2c8d03"
down_revision = "3c9d1e2f4a02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- LoginAttempts ------------------------------------------------------
    op.create_table(
        "LoginAttempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", "ip_address", name="uq_login_attempt"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "idx_login_attempt_locked_until", "LoginAttempts", ["locked_until"]
    )

    # ---- RefreshTokens ------------------------------------------------------
    op.create_table(
        "RefreshTokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("rotated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["id_user"], ["Admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti_hash", name="uq_refresh_jti"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_refresh_user", "RefreshTokens", ["id_user"])
    op.create_index("idx_refresh_expires", "RefreshTokens", ["expires_at"])

    # ---- Tracabilite de validation ------------------------------------------
    # Nullable sans valeur par defaut : les lignes existantes gardent NULL,
    # ce qui se lit correctement comme « valideur inconnu (avant tracabilite) ».
    for table in ("Factures", "NotesDeFrais"):
        op.add_column(table, sa.Column("validated_by", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("validated_at", sa.DateTime(), nullable=True))
        op.create_foreign_key(
            f"fk_{table.lower()}_validated_by",
            table,
            "Admins",
            ["validated_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table in ("Factures", "NotesDeFrais"):
        op.drop_constraint(
            f"fk_{table.lower()}_validated_by", table, type_="foreignkey"
        )
        op.drop_column(table, "validated_at")
        op.drop_column(table, "validated_by")

    op.drop_index("idx_refresh_expires", table_name="RefreshTokens")
    op.drop_index("idx_refresh_user", table_name="RefreshTokens")
    op.drop_table("RefreshTokens")

    op.drop_index("idx_login_attempt_locked_until", table_name="LoginAttempts")
    op.drop_table("LoginAttempts")
