"""Le justificatif de remboursement passe en base, comme les autres pieces.

Il etait la **derniere** famille de documents restee sur le seul disque. Les
justificatifs de notes et de factures y sont passes a la migration
`f6b3d1e8a295`, sur ce raisonnement : la base est sauvegardee par l'hebergeur,
le volume Docker ne l'est pas.

La table gardait un chemin et rien d'autre. Un `docker compose down -v`, un
changement de VPS ou un `volume prune` laissait des remboursements enregistres
sans leur preuve — alors que ce document porte le montant verse, le moyen et
l'approbation.

Revision ID: d0f7b2c5e8a9
Revises: c9e6a4b1d5f8
Create Date: 2026-08-13 22:00:00.000000
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGBLOB


revision = "d0f7b2c5e8a9"
down_revision = "c9e6a4b1d5f8"
branch_labels = None
depends_on = None


COLONNES = (("contenu_pdf", "chemin_pdf"), ("contenu_xlsx", "chemin_xlsx"))

# Meme marge que `f6b3d1e8a295` : le protocole ajoute son en-tete, et froler la
# limite ferait echouer l'ecriture de la plus grosse piece.
MARGE = 2 * 1024 * 1024


def _blob():
    return sa.LargeBinary().with_variant(LONGBLOB(), "mysql")


def _controler_le_paquet(connexion, taille_max: int) -> None:
    if connexion.dialect.name != "mysql" or not taille_max:
        return
    limite = int(connexion.execute(sa.text("SELECT @@max_allowed_packet")).scalar() or 0)
    if limite and limite < taille_max + MARGE:
        raise RuntimeError(
            f"max_allowed_packet vaut {limite} octets, insuffisant pour le plus "
            f"gros justificatif de remboursement ({taille_max} octets). "
            "Aucune donnee n'a ete modifiee."
        )


def upgrade() -> None:
    connexion = op.get_bind()

    for colonne, _ in COLONNES:
        op.add_column("Remboursements", sa.Column(colonne, _blob(), nullable=True))

    lignes = connexion.execute(
        sa.text("SELECT id, chemin_pdf, chemin_xlsx FROM Remboursements")
    ).all()
    if not lignes:
        return

    # Mesurer avant d'ecrire : une migration interrompue au milieu laisserait la
    # moitie des pieces en base et l'autre sur le disque, sans que rien ne dise
    # laquelle est laquelle.
    tailles = []
    for _rid, chemin_pdf, chemin_xlsx in lignes:
        for chemin in (chemin_pdf, chemin_xlsx):
            if chemin and Path(chemin).is_file():
                tailles.append(Path(chemin).stat().st_size)
    _controler_le_paquet(connexion, max(tailles) if tailles else 0)

    charges = absents = 0
    for rid, chemin_pdf, chemin_xlsx in lignes:
        for colonne, chemin in (("contenu_pdf", chemin_pdf), ("contenu_xlsx", chemin_xlsx)):
            fichier = Path(chemin) if chemin else None
            if fichier is None or not fichier.is_file():
                # Deja disparu : la ligne reste lisible avec la colonne a NULL,
                # exactement l'etat dans lequel elle etait avant.
                absents += 1
                continue
            connexion.execute(
                sa.text(f"UPDATE Remboursements SET {colonne} = :donnees WHERE id = :id"),
                {"donnees": fichier.read_bytes(), "id": rid},
            )
            charges += 1

    print(f"Justificatifs de remboursement charges : {charges} ; introuvables : {absents}")


def downgrade() -> None:
    # Les fichiers restent sur le disque tant que le volume est en place — c'est
    # precisement ce sur quoi on ne veut plus compter.
    for colonne, _ in COLONNES:
        op.drop_column("Remboursements", colonne)
