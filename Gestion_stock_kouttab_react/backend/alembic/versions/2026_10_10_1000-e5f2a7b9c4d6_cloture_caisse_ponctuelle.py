"""Buvette : cloture de caisse PONCTUELLE (plusieurs par jour, periode figee).

La cloture n'est plus journaliere : on compte la boite quand on veut, et on la
vide a chaque comptage. Une cloture couvre donc la periode ]dernier comptage ;
saisie], ou « dernier comptage » = la cloture precedente ou la fin du dernier
inventaire termine.

- `CloturesCaisse.periode_debut` / `periode_fin` (UTC naif) et `nb_ventes` ;
- suppression de l'index unique `uq_cloture_caisse_jour` (MariaDB : DROP INDEX),
  remplace par deux index simples (`jour`, `periode_fin`) ;
- retro-remplissage des clotures existantes : elles portaient sur une journee
  de Paris, l'attendu fige ne couvrant que les ventes jusqu'a la saisie, d'ou
  `periode_fin` = min(minuit du lendemain, `created_at`).

Mode hors ligne (`--sql`) : le retro-remplissage est ecrit pour MariaDB avec
`CONVERT_TZ(..., 'Europe/Paris', '+00:00')`. Sans les tables de fuseaux du
serveur, CONVERT_TZ rend NULL et le passage des colonnes en NOT NULL echoue
franchement : rien n'est ecrit a moitie.

Downgrade : recree l'index unique sur `jour`, ce qui echoue s'il existe deja
deux clotures le meme jour (a supprimer ou regrouper a la main d'abord).

Revision ID: e5f2a7b9c4d6
Revises: d4e1f6a8b3c5
Create Date: 2026-10-10 10:00:00.000000
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op


revision = "e5f2a7b9c4d6"
down_revision = "d4e1f6a8b3c5"
branch_labels = None
depends_on = None

PARIS = ZoneInfo("Europe/Paris")


def _minuit_paris_en_utc(jour: date) -> datetime:
    return (
        datetime.combine(jour, time.min, tzinfo=PARIS)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def _utc_vers_paris(instant: datetime) -> datetime:
    return instant.replace(tzinfo=timezone.utc).astimezone(PARIS).replace(tzinfo=None)


def _en_date(valeur) -> date:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    return date.fromisoformat(str(valeur)[:10])


def _en_datetime(valeur) -> datetime | None:
    if valeur is None or isinstance(valeur, datetime):
        return valeur
    return datetime.fromisoformat(str(valeur))


def periode_retroactive(jour: date, created_at: datetime | None) -> tuple[datetime, datetime]:
    """(debut, fin) en UTC naif d'une ancienne cloture journaliere."""
    debut = _minuit_paris_en_utc(jour)
    fin = _minuit_paris_en_utc(jour + timedelta(days=1))
    if created_at is not None:
        fin = max(debut, min(fin, created_at))
    return debut, fin


def _retro_remplir_en_ligne(connexion) -> None:
    clotures = connexion.execute(
        sa.text("SELECT id, jour, created_at FROM CloturesCaisse")
    ).fetchall()
    for identifiant, jour, created_at in clotures:
        debut, fin = periode_retroactive(_en_date(jour), _en_datetime(created_at))
        nb = connexion.execute(
            sa.text(
                "SELECT COUNT(DISTINCT caisse_tx_id) FROM BuvetteSales"
                " WHERE source = 'caisse' AND sumup_tx_code IS NULL"
                " AND COALESCE(sold_at, processed_at) >= :debut"
                " AND COALESCE(sold_at, processed_at) <= :fin"
            ),
            {"debut": _utc_vers_paris(debut), "fin": _utc_vers_paris(fin)},
        ).scalar()
        connexion.execute(
            sa.text(
                "UPDATE CloturesCaisse SET periode_debut = :debut, periode_fin = :fin,"
                " nb_ventes = :nb WHERE id = :id"
            ),
            {"debut": debut, "fin": fin, "nb": int(nb or 0), "id": identifiant},
        )


_SQL_MARIADB = (
    "UPDATE CloturesCaisse SET"
    " periode_debut = CONVERT_TZ(CAST(jour AS DATETIME), 'Europe/Paris', '+00:00'),"
    " periode_fin = GREATEST("
    "CONVERT_TZ(CAST(jour AS DATETIME), 'Europe/Paris', '+00:00'),"
    " LEAST(CONVERT_TZ(CAST(jour + INTERVAL 1 DAY AS DATETIME), 'Europe/Paris', '+00:00'),"
    " created_at))",
    "UPDATE CloturesCaisse c SET nb_ventes = ("
    "SELECT COUNT(DISTINCT s.caisse_tx_id) FROM BuvetteSales s"
    " WHERE s.source = 'caisse' AND s.sumup_tx_code IS NULL"
    " AND COALESCE(s.sold_at, s.processed_at) >= CAST(c.jour AS DATETIME)"
    " AND COALESCE(s.sold_at, s.processed_at)"
    " <= CONVERT_TZ(c.periode_fin, '+00:00', 'Europe/Paris'))",
)


def upgrade() -> None:
    with op.batch_alter_table("CloturesCaisse") as batch:
        batch.add_column(sa.Column("periode_debut", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("periode_fin", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column("nb_ventes", sa.Integer(), nullable=False, server_default="0")
        )
        batch.drop_constraint("uq_cloture_caisse_jour", type_="unique")
        batch.create_index("ix_cloture_caisse_jour", ["jour"])
        batch.create_index("ix_cloture_caisse_periode_fin", ["periode_fin"])

    contexte = op.get_context()
    if contexte.as_sql:
        if contexte.dialect.name == "mysql":
            for requete in _SQL_MARIADB:
                op.execute(requete)
        # Autres dialectes hors ligne : retro-remplissage a faire a la main.
    else:
        _retro_remplir_en_ligne(op.get_bind())

    with op.batch_alter_table("CloturesCaisse") as batch:
        batch.alter_column("periode_debut", existing_type=sa.DateTime(), nullable=False)
        batch.alter_column("periode_fin", existing_type=sa.DateTime(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("CloturesCaisse") as batch:
        batch.drop_index("ix_cloture_caisse_periode_fin")
        batch.drop_index("ix_cloture_caisse_jour")
        batch.drop_column("nb_ventes")
        batch.drop_column("periode_fin")
        batch.drop_column("periode_debut")
        batch.create_unique_constraint("uq_cloture_caisse_jour", ["jour"])
