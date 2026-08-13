"""Le contact devient un fil de discussion, et non plus un courriel sans retour.

`POST /contact` mettait un message en file et n'en gardait rien. La reponse
partait de la boite du comptable, hors de l'application : personne ne pouvait
dire quelles questions restaient sans reponse, ni retrouver ce qui avait ete
repondu six mois plus tot.

Deux tables : le fil et ses messages. Le courriel subsiste, mais il previent
seulement — il ne porte plus la conversation.

Revision ID: c9e6a4b1d5f8
Revises: b8d5f3a0c4e7
Create Date: 2026-08-13 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c9e6a4b1d5f8"
down_revision = "b8d5f3a0c4e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "Conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_user", sa.Integer(), nullable=False),
        sa.Column("destinataire", sa.String(20), nullable=False),
        sa.Column("sujet", sa.String(150), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="ouverte"),
        # Denormalises : ce sont les deux questions que posent les pastilles a
        # chaque chargement de page. Les deduire du dernier message imposerait
        # une sous-requete a chaque fois, vers une base distante.
        sa.Column("attente_equipe", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("non_lu_demandeur", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["id_user"], ["Admins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["closed_by"], ["Admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_conv_user", "Conversations", ["id_user"])
    op.create_index("idx_conv_statut", "Conversations", ["statut"])
    op.create_index("idx_conv_destinataire", "Conversations", ["destinataire"])

    op.create_table(
        "ConversationMessages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_conversation", sa.Integer(), nullable=False),
        sa.Column("id_auteur", sa.Integer(), nullable=True),
        # Instantanes : un compte supprime laisserait sinon des messages
        # anonymes, et un benevole promu comptable ferait retroactivement passer
        # ses anciennes questions pour des reponses de l'equipe.
        sa.Column("auteur_nom", sa.String(150), nullable=False),
        sa.Column("de_l_equipe", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("corps", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["id_conversation"], ["Conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_auteur"], ["Admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_convmsg_conversation", "ConversationMessages", ["id_conversation"])


def downgrade() -> None:
    op.drop_table("ConversationMessages")
    op.drop_table("Conversations")
