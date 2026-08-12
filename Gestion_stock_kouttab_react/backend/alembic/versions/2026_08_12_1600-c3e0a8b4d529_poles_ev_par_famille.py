"""Referentiel des poles revu, et familles d'evenements.

Le client a arrete la liste : EV(T), EV(G), EV(J), Frais generaux, Institut,
Halaqa, Sejour annuel. Les trois poles EV se rattachent a un evenement, les
quatre autres a une categorie de depense.

Ce que devient l'ancien referentiel :

- « Pôle institut » est **renomme** « Institut ». Meme ligne, meme identifiant :
  les factures qui le referencent le suivent. Le recreer a neuf les aurait
  laissees rattachees a un pole disparu du formulaire.
- « Pôle événementiel » et « Local » sont **desactives**, jamais supprimes : des
  pieces les referencent, et leur libelle doit rester lisible.

`Events.type_ev` classe chaque evenement dans une famille. Il se renseigne a la
main : HelloAsso ne connait pas cette classification. Un evenement sans famille
reste propose sous tous les poles EV — sans quoi la premiere synchronisation
viderait les listes, chaque evenement importe arrivant non classe.

Revision ID: c3e0a8b4d529
Revises: b2d9f7a3c418
Create Date: 2026-08-12 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "c3e0a8b4d529"
down_revision = "b2d9f7a3c418"
branch_labels = None
depends_on = None


# Doit rester aligne sur `crud/pole.DEFAULT_POLES` : la migration sert la
# production, la constante sert les tests et le developpement, qui montent le
# schema par `create_all`.
POLES = (
    ("EV(T)", 1, True, "T"),
    ("EV(G)", 2, True, "G"),
    ("EV(J)", 3, True, "J"),
    ("Frais généraux", 4, False, None),
    ("Institut", 5, False, None),
    ("Halaqa", 6, False, None),
    ("Séjour annuel", 7, False, None),
)

RENOMMAGES = (("Pôle institut", "Institut"),)
RETIRES = ("Pôle événementiel", "Local")


def upgrade() -> None:
    op.add_column("Poles", sa.Column("type_evenement", sa.String(10), nullable=True))
    op.add_column("Events", sa.Column("type_ev", sa.String(10), nullable=True))

    connexion = op.get_bind()

    # Renommages avant insertion : sinon « Institut » serait cree en double.
    for ancien, nouveau in RENOMMAGES:
        existe_deja = connexion.execute(
            sa.text("SELECT COUNT(*) FROM Poles WHERE nom = :nom"), {"nom": nouveau}
        ).scalar_one()
        if not existe_deja:
            connexion.execute(
                sa.text("UPDATE Poles SET nom = :nouveau WHERE nom = :ancien"),
                {"nouveau": nouveau, "ancien": ancien},
            )

    presents = {
        nom for (nom,) in connexion.execute(sa.text("SELECT nom FROM Poles")).all()
    }
    for nom, ordre, requiert_evenement, type_evenement in POLES:
        if nom in presents:
            # Deja la (cree par le demarrage de l'application, ou renomme
            # ci-dessus) : on aligne seulement son comportement.
            connexion.execute(
                sa.text(
                    "UPDATE Poles SET ordre = :ordre, is_active = 1, "
                    "requiert_evenement = :requiert, type_evenement = :type "
                    "WHERE nom = :nom"
                ),
                {
                    "ordre": ordre,
                    "requiert": 1 if requiert_evenement else 0,
                    "type": type_evenement,
                    "nom": nom,
                },
            )
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

    for nom in RETIRES:
        connexion.execute(
            sa.text("UPDATE Poles SET is_active = 0 WHERE nom = :nom"), {"nom": nom}
        )


def downgrade() -> None:
    connexion = op.get_bind()

    # Les poles ajoutes ne sont retires que s'ils ne servent a rien : en
    # supprimer un que des factures referencent casserait leur affichage.
    for nom, _ordre, _requiert, _type in POLES:
        utilise = connexion.execute(
            sa.text(
                "SELECT COUNT(*) FROM Factures f JOIN Poles p ON p.id = f.id_pole "
                "WHERE p.nom = :nom"
            ),
            {"nom": nom},
        ).scalar_one()
        if not utilise:
            connexion.execute(
                sa.text("DELETE FROM Poles WHERE nom = :nom"), {"nom": nom}
            )

    for nom in RETIRES:
        connexion.execute(
            sa.text("UPDATE Poles SET is_active = 1 WHERE nom = :nom"), {"nom": nom}
        )
    for ancien, nouveau in RENOMMAGES:
        connexion.execute(
            sa.text("UPDATE Poles SET nom = :ancien WHERE nom = :nouveau"),
            {"ancien": ancien, "nouveau": nouveau},
        )

    op.drop_column("Events", "type_ev")
    op.drop_column("Poles", "type_evenement")
