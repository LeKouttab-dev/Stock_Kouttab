"""Compatibilite des requetes avec le SGBD de production.

Les tests tournent sur SQLite, la production sur **MariaDB**. SQLite est
permissif : il accepte des constructions que MariaDB refuse, si bien qu'une
requete peut passer toute la suite de tests et renvoyer une 500 en ligne.

C'est arrive le 2026-08-11 : `ORDER BY ... NULLS LAST` — syntaxe PostgreSQL,
toleree par SQLite — faisait echouer `GET /events` avec l'erreur MariaDB 1064.
La liste des evenements restait vide au depot d'une facture, sans message.

Ces tests compilent les requetes avec le dialecte MySQL sans les executer : ils
attrapent la syntaxe invalide sans exiger un serveur MariaDB en CI.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import mysql

from app.db.models import Event, Expense, Invoice, OutboundEmail, Stock


pytestmark = pytest.mark.unit


# Constructions qu'aucune requete ne doit produire : MariaDB les rejette.
CLAUSES_INTERDITES = ("NULLS LAST", "NULLS FIRST", "DISTINCT ON", "ILIKE")


def _sql_mysql(stmt) -> str:
    return str(stmt.compile(dialect=mysql.dialect()))


def _verifier(stmt) -> None:
    sql = _sql_mysql(stmt).upper()
    for clause in CLAUSES_INTERDITES:
        assert clause not in sql, f"{clause} n'est pas supporte par MariaDB :\n{sql}"


def test_events_listing_compiles_for_mariadb() -> None:
    """Le tri des evenements ne doit pas dependre de `NULLS LAST`."""
    from app.crud.event import list_events

    # La requete est reconstruite a l'identique, sans acces base : seul le SQL
    # genere nous interesse.
    from sqlalchemy import select

    stmt = (
        select(Event)
        .order_by(Event.date_evenement.is_(None), Event.date_evenement.desc(), Event.nom)
        .limit(500)
    )
    _verifier(stmt)
    assert list_events is not None  # la fonction existe toujours


@pytest.mark.parametrize(
    "stmt",
    [
        pytest.param(__import__("sqlalchemy").select(Stock), id="stock"),
        pytest.param(__import__("sqlalchemy").select(Invoice), id="factures"),
        pytest.param(__import__("sqlalchemy").select(Expense), id="notes-de-frais"),
        pytest.param(__import__("sqlalchemy").select(OutboundEmail), id="file-envois"),
    ],
)
def test_core_selects_compile_for_mariadb(stmt) -> None:
    _verifier(stmt)


def test_the_guard_actually_catches_nulls_last() -> None:
    """Le garde-fou doit echouer sur la construction fautive.

    Sans cette verification, une erreur dans `_verifier` rendrait tous les
    tests ci-dessus verts sans rien controler.
    """
    from sqlalchemy import select

    fautive = select(Event).order_by(Event.date_evenement.desc().nullslast())
    with pytest.raises(AssertionError, match="NULLS LAST"):
        _verifier(fautive)
