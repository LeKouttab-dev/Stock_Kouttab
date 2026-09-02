"""Met au format PDF les releves d'identite bancaire deja deposes.

Le schema ne bouge pas : seul le CONTENU des colonnes `rib_document`,
`rib_document_nom` et `rib_document_type` change — d'ou une migration de donnees,
sans `alter_column`.

Pourquoi ici plutot que dans un script a lancer a la main : le deploiement
execute deja `alembic upgrade head` avant de redemarrer l'API. Et surtout, le
depot d'une note de frais exige desormais un RIB **au format PDF** : sans cette
migration, tous ceux qui avaient depose une photo quand c'etait encore accepte
se retrouveraient bloques, sans comprendre pourquoi. Une contrainte nouvelle sur
un depot existant se livre avec la mise en conformite du stock existant.

Le format d'entree, lui, reste libre : `POST /users/me/rib-document` convertit
desormais a l'enregistrement. Refuser la photo aurait bloque ceux qui n'ont que
leur telephone.

Un document illisible n'arrete pas la migration : il est laisse tel quel et
journalise. Le controle pose sur le depot demandera a son proprietaire d'en
deposer un autre — c'est un meilleur sort qu'un deploiement bloque pour tous.

Revision ID: e8b2f4a7c1d5
Revises: d7a1c9e6b3f8
Create Date: 2026-09-02 10:00:00.000000
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op

from app.core.logger import get_logger
from app.services import pdf


revision = "e8b2f4a7c1d5"
down_revision = "d7a1c9e6b3f8"
branch_labels = None
depends_on = None


logger = get_logger("migration.rib_pdf")


def upgrade() -> None:
    connexion = op.get_bind()
    lignes = connexion.execute(
        sa.text(
            "SELECT id, rib_document, rib_document_nom FROM Admins "
            "WHERE rib_document IS NOT NULL "
            "AND (rib_document_type IS NULL OR rib_document_type <> 'application/pdf')"
        )
    ).fetchall()

    for identifiant, document, nom in lignes:
        octets = bytes(document)
        try:
            contenu, converti = pdf.octets_en_pdf(octets)
        except Exception as exc:  # noqa: BLE001 — img2pdf et Pillow levent des types varies
            logger.warning(
                "RIB du compte %s illisible, laisse en l'etat : %s", identifiant, exc
            )
            continue

        if not converti:
            # Deja un PDF, mal etiquete : on corrige l'etiquette sans toucher aux
            # octets, sinon le controle du depot le refuserait a tort.
            connexion.execute(
                sa.text(
                    "UPDATE Admins SET rib_document_type = 'application/pdf' WHERE id = :id"
                ),
                {"id": identifiant},
            )
            continue

        connexion.execute(
            sa.text(
                "UPDATE Admins SET rib_document = :contenu, rib_document_nom = :nom, "
                "rib_document_type = 'application/pdf' WHERE id = :id"
            ),
            {
                "contenu": contenu,
                "nom": f"{Path(nom or 'rib').stem}.pdf"[:255],
                "id": identifiant,
            },
        )


def downgrade() -> None:
    """Rien a defaire.

    On ne reconstruit pas la photo d'origine depuis le PDF qui l'enveloppe, et
    l'ancienne version du code sait parfaitement servir un PDF — elle en acceptait
    deja. Le retour arriere ne laisse donc rien d'illisible derriere lui.
    """
