"""Add barcode columns on Stock and BuvetteProducts.

Revision ID: 3c9d1e2f4a02
Revises: 7a1b3c5d9e01
Create Date: 2026-05-04 09:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "3c9d1e2f4a02"
down_revision = "7a1b3c5d9e01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- Stock --------------------------------------------------------------
    op.add_column(
        "Stock",
        sa.Column("barcode", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_stock_barcode",
        "Stock",
        ["barcode"],
        unique=True,
    )

    # ---- BuvetteProducts ----------------------------------------------------
    op.add_column(
        "BuvetteProducts",
        sa.Column("barcode", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_buvette_products_barcode",
        "BuvetteProducts",
        ["barcode"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_buvette_products_barcode", table_name="BuvetteProducts")
    op.drop_column("BuvetteProducts", "barcode")

    op.drop_index("ix_stock_barcode", table_name="Stock")
    op.drop_column("Stock", "barcode")
