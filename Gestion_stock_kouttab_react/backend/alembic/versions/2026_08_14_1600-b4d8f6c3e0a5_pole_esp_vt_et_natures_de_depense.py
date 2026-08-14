"""Pole ESP-VT, et la nature de la depense sur toutes les pieces.

Trois changements, tous additifs — aucune colonne n'est touchee, aucune ligne
existante n'est invalidee :

1. **Le pole `ESP-VT`** rejoint le referentiel. Il ne se rattache pas a un
   evenement : une depense de l'espace vente est un achat de fonctionnement,
   pas une sortie datee.
2. **Quatre natures de depense** demandees par le client : mobilier et petit
   equipement, fournitures administratives, entretien, receptions.
3. **`Autre` passe en fin de liste** (`ordre = 99`). Elle se retrouvait au
   milieu des nouvelles entrees, et une categorie fourre-tout offerte avant les
   categories precises se choisit par defaut.

Rien ici ne rend `id_categorie` obligatoire en base : la colonne reste
nullable. Les pieces deposees sous un pole evenementiel avant ce jour n'ont pas
de categorie et n'en auront jamais — la leur inventer retroactivement inscrirait
dans la comptabilite une information que personne n'a saisie. Seuls les
**nouveaux** depots l'exigent, et c'est `crud/rattachement.resoudre` qui le
controle.

Revision ID: b4d8f6c3e0a5
Revises: a3c7e5b2f9d4
Create Date: 2026-08-14 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b4d8f6c3e0a5"
down_revision = "a3c7e5b2f9d4"
branch_labels = None
depends_on = None


# Doivent rester alignes sur `crud/pole.DEFAULT_POLES` et
# `crud/expense_category.DEFAULT_CATEGORIES` : la migration sert la production,
# les constantes servent les tests et le developpement, qui montent le schema
# par `create_all` et ne jouent jamais les migrations.
POLES = (("ESP-VT", 8, False, None),)

CATEGORIES = (
    ("Mobilier, immobilier et petit équipement", 5),
    ("Fournitures administratives", 6),
    ("Entretien", 7),
    ("Réceptions (repas, déplacements, nourriture)", 8),
)


def upgrade() -> None:
    connexion = op.get_bind()

    def existe(table: str, nom: str) -> bool:
        """Le `ensure_default_*` du demarrage a pu prendre les devants.

        Si l'application a tourne avant que la migration ne soit jouee, la ligne
        est deja la et `nom` est UNIQUE : un insert sec ferait echouer toute la
        migration.
        """
        trouve = connexion.execute(
            sa.text(f"SELECT 1 FROM {table} WHERE nom = :nom LIMIT 1"), {"nom": nom}
        ).first()
        return trouve is not None

    for nom, ordre, requiert_evenement, type_evenement in POLES:
        if existe("Poles", nom):
            continue
        connexion.execute(
            sa.text(
                "INSERT INTO Poles (nom, is_default, is_active, ordre, "
                "requiert_evenement, type_evenement) "
                "VALUES (:nom, 1, 1, :ordre, :requiert, :type)"
            ),
            {
                "nom": nom,
                "ordre": ordre,
                "requiert": 1 if requiert_evenement else 0,
                "type": type_evenement,
            },
        )

    for nom, ordre in CATEGORIES:
        if existe("CategoriesDepense", nom):
            continue
        connexion.execute(
            sa.text(
                "INSERT INTO CategoriesDepense (nom, is_default, is_active, ordre) "
                "VALUES (:nom, 1, 1, :ordre)"
            ),
            {"nom": nom, "ordre": ordre},
        )

    connexion.execute(
        sa.text("UPDATE CategoriesDepense SET ordre = 99 WHERE nom = 'Autre'")
    )


def downgrade() -> None:
    connexion = op.get_bind()

    connexion.execute(
        sa.text("UPDATE CategoriesDepense SET ordre = 5 WHERE nom = 'Autre'")
    )

    # Desactivation, jamais suppression : une piece peut deja les referencer, et
    # son libelle doit rester lisible. C'est la regle appliquee a chaque retrait
    # du referentiel depuis `c3e0a8b4d529`.
    for nom, _ordre in CATEGORIES:
        connexion.execute(
            sa.text("UPDATE CategoriesDepense SET is_active = 0 WHERE nom = :nom"),
            {"nom": nom},
        )
    for nom, _ordre, _requiert, _type in POLES:
        connexion.execute(
            sa.text("UPDATE Poles SET is_active = 0 WHERE nom = :nom"), {"nom": nom}
        )
