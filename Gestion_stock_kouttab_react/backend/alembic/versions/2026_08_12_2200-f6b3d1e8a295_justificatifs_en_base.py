"""Stocke les justificatifs EN BASE plutot que sur le seul disque du VPS.

Les fichiers ne vivaient que dans un volume Docker : la table ne gardait qu'un
chemin, et perdre la machine revenait a perdre des pieces comptables qu'on est
tenu de conserver plusieurs annees. La base, elle, est sauvegardee par O2Switch.

Ce choix tient a la mesure : **11 Mo pour l'ensemble des justificatifs, 4,5 Mo
pour le plus gros fichier**. A cette echelle, la base est le bon endroit et
supprime le probleme au lieu d'ajouter un mecanisme de sauvegarde de plus. Il en
irait autrement avec plusieurs gigaoctets.

`chemin_fichier` est conserve : il documente l'origine du fichier et sert de
repli tant que la colonne `contenu` est vide.

Revision ID: f6b3d1e8a295
Revises: e5a2c0d7f184
Create Date: 2026-08-12 22:00:00.000000
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGBLOB


revision = "f6b3d1e8a295"
down_revision = "e5a2c0d7f184"
branch_labels = None
depends_on = None


TABLES = ("FichiersNotesDeFrais", "FichiersFactures")

# Marge exigee au-dessus du plus gros fichier : le protocole ajoute son
# en-tete, et frôler la limite ferait echouer l'ecriture d'une seule piece — la
# plus grosse, celle qu'on aurait le plus de mal a recuperer.
MARGE = 2 * 1024 * 1024


def _blob():
    return sa.LargeBinary().with_variant(LONGBLOB(), "mysql")


def _controler_le_paquet(connexion, taille_max: int) -> None:
    """Refuse de migrer si MySQL n'accepte pas le plus gros fichier.

    Verifie AVANT d'ecrire quoi que ce soit : une migration qui s'arrete au
    milieu laisserait la moitie des pieces en base et l'autre sur le disque,
    sans que rien ne dise laquelle est laquelle.
    """
    if connexion.dialect.name != "mysql":
        return
    limite = int(connexion.execute(sa.text("SELECT @@max_allowed_packet")).scalar() or 0)
    if limite and limite < taille_max + MARGE:
        raise RuntimeError(
            f"max_allowed_packet vaut {limite} octets, insuffisant pour le plus "
            f"gros justificatif ({taille_max} octets). Demander son relevement a "
            "l'hebergeur, ou reduire MAX_UPLOAD_MB. Aucune donnee n'a ete modifiee."
        )


def upgrade() -> None:
    connexion = op.get_bind()

    for table in TABLES:
        op.add_column(table, sa.Column("contenu", _blob(), nullable=True))

    # --- Chargement des fichiers existants -----------------------------------
    lignes: list[tuple[str, int, str]] = []
    for table in TABLES:
        for rid, chemin in connexion.execute(
            sa.text(f"SELECT id, chemin_fichier FROM {table} WHERE chemin_fichier <> ''")
        ).all():
            lignes.append((table, rid, chemin))

    if not lignes:
        return

    tailles = {}
    for table, rid, chemin in lignes:
        fichier = Path(chemin)
        if fichier.is_file():
            tailles[(table, rid)] = fichier.stat().st_size

    if tailles:
        _controler_le_paquet(connexion, max(tailles.values()))

    charges = absents = 0
    for table, rid, chemin in lignes:
        fichier = Path(chemin)
        if not fichier.is_file():
            # Fichier deja disparu : on ne bloque pas la migration pour autant.
            # La ligne reste lisible, avec `contenu` a NULL — exactement l'etat
            # dans lequel elle etait avant.
            absents += 1
            continue
        connexion.execute(
            sa.text(f"UPDATE {table} SET contenu = :donnees WHERE id = :id"),
            {"donnees": fichier.read_bytes(), "id": rid},
        )
        charges += 1

    print(f"Justificatifs charges en base : {charges} ; introuvables sur disque : {absents}")


def downgrade() -> None:
    # Les fichiers restent sur le disque : retirer la colonne ne perd rien tant
    # que le volume est en place.
    for table in TABLES:
        op.drop_column(table, "contenu")
