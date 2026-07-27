"""Add Buvette tables (BuvetteProducts, BuvetteSales).

Revision ID: 7a1b3c5d9e01
Revises:
Create Date: 2026-05-03 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7a1b3c5d9e01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "BuvetteProducts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("helloasso_tier_id", sa.Integer(), nullable=True, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seuil_alerte", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("emoji", sa.String(length=10), nullable=True, server_default="🥤"),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "alert_sent", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "idx_buvette_prod_tier",
        "BuvetteProducts",
        ["helloasso_tier_id"],
    )
    op.create_index(
        "idx_buvette_prod_active",
        "BuvetteProducts",
        ["is_active"],
    )

    op.create_table(
        "BuvetteSales",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("helloasso_order_id", sa.Integer(), nullable=True),
        sa.Column("helloasso_payment_id", sa.Integer(), nullable=True),
        sa.Column("helloasso_item_id", sa.Integer(), nullable=True),
        sa.Column("buvette_product_id", sa.Integer(), nullable=True),
        sa.Column("product_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column(
            "quantity_sold", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "amount_cents", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("customer_first_name", sa.String(length=255), nullable=True),
        sa.Column("customer_last_name", sa.String(length=255), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("raw_event", sa.Text(), nullable=True),
        sa.Column("sold_at", sa.DateTime(), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["buvette_product_id"],
            ["BuvetteProducts.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "helloasso_payment_id",
            "helloasso_item_id",
            name="uq_sale_payment_item",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_buvette_sale_order", "BuvetteSales", ["helloasso_order_id"])
    op.create_index(
        "idx_buvette_sale_payment", "BuvetteSales", ["helloasso_payment_id"]
    )
    op.create_index("idx_buvette_sale_item", "BuvetteSales", ["helloasso_item_id"])
    op.create_index("idx_buvette_sale_product", "BuvetteSales", ["buvette_product_id"])
    op.create_index("idx_buvette_sale_processed", "BuvetteSales", ["processed_at"])


def downgrade() -> None:
    op.drop_index("idx_buvette_sale_processed", table_name="BuvetteSales")
    op.drop_index("idx_buvette_sale_product", table_name="BuvetteSales")
    op.drop_index("idx_buvette_sale_item", table_name="BuvetteSales")
    op.drop_index("idx_buvette_sale_payment", table_name="BuvetteSales")
    op.drop_index("idx_buvette_sale_order", table_name="BuvetteSales")
    op.drop_table("BuvetteSales")

    op.drop_index("idx_buvette_prod_active", table_name="BuvetteProducts")
    op.drop_index("idx_buvette_prod_tier", table_name="BuvetteProducts")
    op.drop_table("BuvetteProducts")
