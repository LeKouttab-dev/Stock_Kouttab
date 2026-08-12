"""Cadence des relances : tous les 3 jours, 5 fois au maximum.

Le point sensible n'est pas d'envoyer, c'est de **s'arreter**. Un rappel qui
part tous les quarts d'heure, ou qui continue apres reception de la piece, se
fait mettre en filtre — et la relance suivante, celle qui comptait, n'est plus
lue.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.crud import ticket as ticket_crud
from app.db.models import JustificatifTicket


pytestmark = pytest.mark.unit


T0 = datetime(2026, 8, 12, 9, 0, 0)


def _ticket(db: Session, benevole, **kw) -> JustificatifTicket:
    ticket = ticket_crud.create_ticket(
        db, id_user=benevole.id, libelle=kw.pop("libelle", "Facture Metro du 3 août")
    )
    for champ, valeur in kw.items():
        setattr(ticket, champ, valeur)
    db.commit()
    return ticket


def test_un_ticket_neuf_est_relancable(db_session: Session, benevole_user):
    """Le premier rappel part sans attendre : signaler trois jours plus tard
    une demande qui vient d'etre ouverte ne servirait personne."""
    ticket = _ticket(db_session, benevole_user, created_at=T0)
    assert ticket_crud.doit_relancer(ticket, maintenant=T0)


def test_pas_de_relance_avant_trois_jours(db_session: Session, benevole_user):
    ticket = _ticket(db_session, benevole_user, created_at=T0, dernier_rappel_at=T0)
    assert not ticket_crud.doit_relancer(ticket, maintenant=T0 + timedelta(days=2))
    assert ticket_crud.doit_relancer(ticket, maintenant=T0 + timedelta(days=3))


def test_le_quota_arrete_les_relances(db_session: Session, benevole_user):
    """Cinq rappels et plus rien : le ticket reste ouvert, mais se tait."""
    ticket = _ticket(
        db_session,
        benevole_user,
        created_at=T0,
        dernier_rappel_at=T0,
        rappels_envoyes=ticket_crud.RAPPELS_MAX,
    )
    assert not ticket_crud.doit_relancer(ticket, maintenant=T0 + timedelta(days=30))
    assert ticket.statut == JustificatifTicket.STATUT_OUVERT


def test_un_ticket_clos_ne_relance_plus(db_session: Session, benevole_user):
    """La piece est arrivee : continuer a la reclamer serait le meilleur moyen
    d'etre ignore la prochaine fois."""
    ticket = _ticket(db_session, benevole_user, created_at=T0)
    ticket_crud.close_ticket(db_session, ticket.id)
    db_session.refresh(ticket)
    assert not ticket_crud.doit_relancer(ticket, maintenant=T0 + timedelta(days=10))


def test_la_selection_ne_retient_que_les_tickets_dus(
    db_session: Session, benevole_user, compta_user
):
    du = _ticket(db_session, benevole_user, created_at=T0 - timedelta(days=5))
    trop_recent = _ticket(
        db_session, compta_user, created_at=T0, dernier_rappel_at=T0
    )

    a_relancer = ticket_crud.tickets_a_relancer(db_session, maintenant=T0)

    ids = [t.id for t in a_relancer]
    assert du.id in ids
    assert trop_recent.id not in ids


def test_marquer_relance_incremente_et_date(db_session: Session, benevole_user):
    ticket = _ticket(db_session, benevole_user, created_at=T0)
    ticket_crud.marquer_relance(db_session, ticket, maintenant=T0)

    assert ticket.rappels_envoyes == 1
    assert ticket.dernier_rappel_at == T0
    # Le suivant attend son tour.
    assert not ticket_crud.doit_relancer(ticket, maintenant=T0 + timedelta(days=1))


def test_cinq_relances_puis_silence(db_session: Session, benevole_user):
    """Deroulement complet, comme le worker l'executerait."""
    ticket = _ticket(db_session, benevole_user, created_at=T0)
    instant = T0

    for tour in range(ticket_crud.RAPPELS_MAX):
        assert ticket_crud.doit_relancer(ticket, maintenant=instant), f"tour {tour}"
        ticket_crud.marquer_relance(db_session, ticket, maintenant=instant)
        instant += timedelta(days=3)

    assert ticket.rappels_envoyes == ticket_crud.RAPPELS_MAX
    assert not ticket_crud.doit_relancer(ticket, maintenant=instant + timedelta(days=90))
