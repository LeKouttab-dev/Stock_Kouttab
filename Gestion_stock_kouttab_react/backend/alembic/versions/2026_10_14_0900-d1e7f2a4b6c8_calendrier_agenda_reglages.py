"""Calendrier : salle habituelle et nom court par agenda Google.

Nouvelle table `CalendrierAgendaReglages`, vide a la creation :

- `salle` : la salle habituelle de l'agenda, pour les trois quarts de cours qui
  n'en reservent aucune dans Google. Une salle reellement reservee dans
  l'evenement l'emporte toujours.
- `nom_court` : le libelle de la carte quand la regle de raccourcissement tombe
  mal (un cas sur quarante-cinq a ce jour).

Purement additive : aucune table existante n'est touchee, et le calendrier
fonctionne table vide — tous les agendas tombent alors dans la colonne
« Autre », ce qui est l'etat d'aujourd'hui.

Aucun remplissage automatique : deviner la salle d'un agenda sans verification
humaine ferait dire a l'ecran qu'un cours se tient quelque part alors que rien
ne le reserve. L'ecran de reglage propose une deduction, une personne valide.

Revision ID: d1e7f2a4b6c8
Revises: c9d6e1f3a8b0
Create Date: 2026-10-14 09:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d1e7f2a4b6c8"
down_revision = "c9d6e1f3a8b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "CalendrierAgendaReglages",
        # Cle de substitution : `agenda_id` fait 60 a 70 caracteres et un
        # String(255) utf8mb4 en cle primaire pese 1020 octets d'index, au-dela
        # des 767 qu'autorise InnoDB en format de ligne COMPACT.
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("agenda_id", sa.String(length=255), nullable=False),
        sa.Column("agenda_nom", sa.String(length=255), nullable=True),
        sa.Column("salle", sa.String(length=16), nullable=True),
        sa.Column("nom_court", sa.String(length=32), nullable=True),
        sa.Column("modifie_par", sa.String(length=255), nullable=True),
        sa.Column(
            "modifie_le",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agenda_id", name="uq_calendrier_agenda"),
    )


def downgrade() -> None:
    op.drop_table("CalendrierAgendaReglages")
