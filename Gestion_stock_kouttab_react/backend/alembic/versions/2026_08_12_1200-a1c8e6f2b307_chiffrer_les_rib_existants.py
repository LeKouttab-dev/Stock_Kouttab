"""Chiffre au repos les RIB deja enregistres.

Le schema ne bouge pas : `Admins.rib` reste un VARCHAR(255), et une valeur
chiffree y tient. Seul le CONTENU change — d'ou une migration de donnees, sans
`alter_column`.

Pourquoi ici plutot que dans un script a lancer a la main : le deploiement
execute deja `alembic upgrade head` avant de redemarrer l'API. La conversion se
fait donc une fois, au bon moment, sans etape supplementaire a ne pas oublier.
Et elle doit etre faite en bloc : reecrire un profil ne convertit pas un RIB
inchange (l'ORM ne voit aucune modification et n'emet aucun UPDATE), si bien
que sans cette migration, le RIB de tous ceux qui n'y retouchent jamais
resterait en clair indefiniment.

**La cle doit etre en place avant de migrer.** Sans `RIB_ENCRYPTION_KEY` dans
le `.env`, la migration s'arrete et ne convertit rien plutot que de laisser la
base a moitie chiffree.

Revision ID: a1c8e6f2b307
Revises: 9b7d0e5f1a06
Create Date: 2026-08-12 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core import crypto


revision = "a1c8e6f2b307"
down_revision = "9b7d0e5f1a06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connexion = op.get_bind()
    lignes = connexion.execute(
        sa.text("SELECT id, rib FROM Admins WHERE rib IS NOT NULL AND rib <> ''")
    ).fetchall()

    a_convertir = [(rid, rib) for rid, rib in lignes if not crypto.est_chiffre(rib)]
    if not a_convertir:
        return

    if not crypto.cle_disponible():
        raise RuntimeError(
            f"{len(a_convertir)} RIB en clair a chiffrer, mais RIB_ENCRYPTION_KEY "
            "est absente du .env. Generer une cle avec :\n"
            '  python -c "import base64, os; '
            'print(base64.urlsafe_b64encode(os.urandom(32)).decode())"\n'
            "puis relancer la migration. Aucune donnee n'a ete modifiee."
        )

    for rid, rib in a_convertir:
        connexion.execute(
            sa.text("UPDATE Admins SET rib = :rib WHERE id = :id"),
            {"rib": crypto.chiffrer(rib), "id": rid},
        )


def downgrade() -> None:
    """Remet les RIB en clair.

    Prevu pour le retour arriere : l'ancienne version du code lit la colonne
    telle quelle et afficherait `gcm1:...` a la comptabilite. La cle est donc
    requise ici aussi — sans elle, le retour arriere echoue au lieu de laisser
    des valeurs illisibles derriere lui.
    """
    connexion = op.get_bind()
    lignes = connexion.execute(
        sa.text("SELECT id, rib FROM Admins WHERE rib IS NOT NULL AND rib <> ''")
    ).fetchall()

    chiffres = [(rid, rib) for rid, rib in lignes if crypto.est_chiffre(rib)]
    if not chiffres:
        return

    if not crypto.cle_disponible():
        raise RuntimeError(
            "RIB_ENCRYPTION_KEY absente : impossible de dechiffrer. "
            "Restaurer la cle avant de revenir en arriere."
        )

    for rid, rib in chiffres:
        connexion.execute(
            sa.text("UPDATE Admins SET rib = :rib WHERE id = :id"),
            {"rib": crypto.dechiffrer(rib), "id": rid},
        )
