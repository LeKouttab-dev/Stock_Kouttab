"""Compte systeme « Tablette buvette » (ecran Personnel de la tablette de caisse).

L'ecran « Personnel » de la tablette affiche l'application stock elle-meme, sous
un compte PARTAGE : pas de mot de passe, la personne donne seulement son nom,
qui signe chaque action (« Nom (tablette) »). La session s'ouvre par
`POST /api/v1/auth/caisse/session`, gardee par la cle de la caisse.

- `username` = `tablette_buvette`, role `AdminStock` (buvette seule), actif ;
- `password_hash` INUTILISABLE (ni bcrypt ni SHA-256 : aucun mot de passe ne lui
  correspond ; la connexion par formulaire le refuse en plus explicitement) ;
- `email` = `tablette-buvette@lekouttab.fr` : identifiant interne, exclu des
  destinataires des courriels de la buvette.

Idempotente : si un compte porte deja cet identifiant, rien n'est ecrit.
Downgrade : supprime le compte (ses jetons de rafraichissement d'abord). Les
noms d'auteur figes (« Nom (tablette) ») restent dans les tables metier.

Revision ID: f6a3b8c0d5e7
Revises: e5f2a7b9c4d6
Create Date: 2026-10-10 14:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f6a3b8c0d5e7"
down_revision = "e5f2a7b9c4d6"
branch_labels = None
depends_on = None


# Recopies de `app.core.tablette` : une migration ne doit pas dependre du code
# applicatif, qui peut changer apres elle.
USERNAME = "tablette_buvette"
EMAIL = "tablette-buvette@lekouttab.fr"
MOT_DE_PASSE_INUTILISABLE = "!compte-systeme-tablette-sans-mot-de-passe"


def upgrade() -> None:
    bind = op.get_bind()
    existe = bind.execute(
        sa.text("SELECT id FROM Admins WHERE username = :u"), {"u": USERNAME}
    ).first()
    if existe is not None:
        return
    # `created_at` / `updated_at` : valeurs par defaut de la table.
    bind.execute(
        sa.text(
            "INSERT INTO Admins (username, password_hash, role, validation_status,"
            " nom, prenom, email)"
            " VALUES (:u, :h, 'AdminStock', 'active', 'buvette', 'Tablette', :e)"
        ),
        {"u": USERNAME, "h": MOT_DE_PASSE_INUTILISABLE, "e": EMAIL},
    )


def downgrade() -> None:
    bind = op.get_bind()
    ligne = bind.execute(
        sa.text("SELECT id FROM Admins WHERE username = :u"), {"u": USERNAME}
    ).first()
    if ligne is None:
        return
    inspecteur = sa.inspect(bind)
    if inspecteur.has_table("RefreshTokens"):
        bind.execute(
            sa.text("DELETE FROM RefreshTokens WHERE id_user = :i"), {"i": ligne[0]}
        )
    bind.execute(sa.text("DELETE FROM Admins WHERE id = :i"), {"i": ligne[0]})
