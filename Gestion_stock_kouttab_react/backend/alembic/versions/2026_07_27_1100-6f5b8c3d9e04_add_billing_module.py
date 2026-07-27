"""Billing module: Poles, Events, OutboundEmails and invoice metadata.

ATTENTION : ne jamais regenerer ce fichier avec ``alembic revision
--autogenerate``. L'historique Alembic ne connait pas les dix tables
historiques ; un autogenerate voudrait les CREER et detruirait la production.

Revision ID: 6f5b8c3d9e04
Revises: 5e4a7b2c8d03
Create Date: 2026-07-27 11:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "6f5b8c3d9e04"
down_revision = "5e4a7b2c8d03"
branch_labels = None
depends_on = None


DEFAULT_POLES = [
    {"nom": "Pôle événementiel", "is_default": True, "is_active": True, "ordre": 1},
    {"nom": "Pôle institut", "is_default": True, "is_active": True, "ordre": 2},
    {"nom": "Local", "is_default": True, "is_active": True, "ordre": 3},
]


def upgrade() -> None:
    # ---- Poles --------------------------------------------------------------
    poles = op.create_table(
        "Poles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nom", sa.String(length=120), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nom", name="uq_pole_nom"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_pole_nom", "Poles", ["nom"])
    op.create_index("idx_pole_active", "Poles", ["is_active"])
    op.bulk_insert(poles, DEFAULT_POLES)

    # ---- Events -------------------------------------------------------------
    op.create_table(
        "Events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("helloasso_form_slug", sa.String(length=255), nullable=True),
        sa.Column("helloasso_form_type", sa.String(length=50), nullable=True),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("date_evenement", sa.Date(), nullable=True),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("helloasso_state", sa.String(length=20), nullable=True),
        sa.Column(
            "source", sa.String(length=20), nullable=False, server_default="helloasso"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "helloasso_form_type", "helloasso_form_slug", name="uq_event_helloasso"
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_event_nom", "Events", ["nom"])
    op.create_index("idx_event_date", "Events", ["date_evenement"])
    op.create_index("idx_event_active", "Events", ["is_active"])

    # ---- OutboundEmails -----------------------------------------------------
    op.create_table(
        "OutboundEmails",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("recipients", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("attachments", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_outmail_status", "OutboundEmails", ["status"])
    op.create_index("idx_outmail_entity", "OutboundEmails", ["entity_type", "entity_id"])
    op.create_index("idx_outmail_retry", "OutboundEmails", ["status", "next_retry_at"])

    # ---- Metadonnees comptables sur Factures --------------------------------
    # Toutes nullables : la table contient des lignes en production et un
    # DEFAULT '' polluerait l'historique avec de fausses valeurs.
    op.add_column("Factures", sa.Column("id_pole", sa.Integer(), nullable=True))
    op.add_column("Factures", sa.Column("pole", sa.String(length=120), nullable=True))
    op.add_column("Factures", sa.Column("id_event", sa.Integer(), nullable=True))
    op.add_column("Factures", sa.Column("evenement", sa.String(length=255), nullable=True))
    op.add_column("Factures", sa.Column("date_evenement", sa.Date(), nullable=True))
    op.add_column("Factures", sa.Column("fournisseur", sa.String(length=255), nullable=True))
    op.add_column("Factures", sa.Column("montant", sa.DECIMAL(10, 2), nullable=True))
    op.create_index("idx_facture_pole", "Factures", ["id_pole"])
    op.create_index("idx_facture_event", "Factures", ["id_event"])
    op.create_index("idx_facture_date_evenement", "Factures", ["date_evenement"])


def downgrade() -> None:
    op.drop_index("idx_facture_date_evenement", table_name="Factures")
    op.drop_index("idx_facture_event", table_name="Factures")
    op.drop_index("idx_facture_pole", table_name="Factures")
    for column in (
        "montant",
        "fournisseur",
        "date_evenement",
        "evenement",
        "id_event",
        "pole",
        "id_pole",
    ):
        op.drop_column("Factures", column)

    op.drop_index("idx_outmail_retry", table_name="OutboundEmails")
    op.drop_index("idx_outmail_entity", table_name="OutboundEmails")
    op.drop_index("idx_outmail_status", table_name="OutboundEmails")
    op.drop_table("OutboundEmails")

    op.drop_index("idx_event_active", table_name="Events")
    op.drop_index("idx_event_date", table_name="Events")
    op.drop_index("idx_event_nom", table_name="Events")
    op.drop_table("Events")

    op.drop_index("idx_pole_active", table_name="Poles")
    op.drop_index("idx_pole_nom", table_name="Poles")
    op.drop_table("Poles")
