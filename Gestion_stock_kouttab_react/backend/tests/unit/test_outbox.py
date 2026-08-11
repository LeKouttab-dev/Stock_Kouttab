"""File d'attente des envois comptables.

Ce que ces tests protegent : avant l'outbox, un echec SMTP etait totalement
invisible (BackgroundTask + exception avalee). Le comptable ne recevait rien et
personne ne l'apprenait avant la cloture.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from app.db.models import OutboundEmail
from app.services import outbox


pytestmark = pytest.mark.unit


def _enqueue(db, **overrides) -> OutboundEmail:
    payload = {
        "kind": "invoice_compta",
        "entity_type": "invoice",
        "entity_id": 1,
        "recipients": ["comptabilite@lekouttab.fr"],
        "subject": "[Facture] Local — Gala — 14/03/2026",
        "body": "corps",
        "attachments": [],
    }
    payload.update(overrides)
    return outbox.enqueue(db, **payload)


# ---- Mise en file -----------------------------------------------------------


def test_enqueue_creates_a_pending_row(db_session) -> None:
    row = _enqueue(db_session)
    assert row.status == outbox.STATUS_PENDING
    assert row.attempts == 0
    assert json.loads(row.recipients) == ["comptabilite@lekouttab.fr"]


def test_enqueue_without_recipient_still_records_the_intent(db_session) -> None:
    """COMPTA_EMAIL non configure : rien ne doit etre perdu."""
    row = _enqueue(db_session, recipients=[])
    assert row.status == outbox.STATUS_PENDING
    assert row.attempts == 0
    assert "COMPTA_EMAIL" in (row.last_error or "")


def test_enqueue_truncates_an_overlong_subject(db_session) -> None:
    row = _enqueue(db_session, subject="S" * 400)
    assert len(row.subject) <= 255


# ---- Verrou -----------------------------------------------------------------


def test_acquire_succeeds_once_then_fails(db_session) -> None:
    """Deux executions concurrentes du cron ne doivent pas envoyer en double."""
    row = _enqueue(db_session)
    assert outbox._acquire(db_session, row.id) is True
    assert outbox._acquire(db_session, row.id) is False


def test_acquire_refuses_an_already_sent_row(db_session) -> None:
    row = _enqueue(db_session)
    outbox.mark_sent(db_session, row)
    assert outbox._acquire(db_session, row.id) is False


def test_acquire_accepts_a_failed_row(db_session) -> None:
    row = _enqueue(db_session)
    outbox.mark_failed(db_session, row, "SMTP indisponible")
    assert outbox._acquire(db_session, row.id) is True


def test_stale_locks_are_released(db_session) -> None:
    """Un process tue en plein envoi ne doit pas bloquer la piece a jamais."""
    row = _enqueue(db_session)
    outbox._acquire(db_session, row.id)
    row = db_session.get(OutboundEmail, row.id)
    row.locked_at = outbox._now() - outbox.STALE_LOCK_AFTER - timedelta(minutes=1)
    db_session.commit()

    assert outbox.reset_stale_locks(db_session) == 1
    db_session.refresh(row)
    assert row.status == outbox.STATUS_PENDING


def test_recent_locks_are_preserved(db_session) -> None:
    row = _enqueue(db_session)
    outbox._acquire(db_session, row.id)
    assert outbox.reset_stale_locks(db_session) == 0


# ---- Backoff ----------------------------------------------------------------


def test_retry_delay_grows_strictly(db_session) -> None:
    row = _enqueue(db_session)
    delays = []
    for _ in range(3):
        outbox.mark_failed(db_session, row, "erreur")
        delays.append(row.next_retry_at)
        row.status = outbox.STATUS_FAILED
    assert delays[0] < delays[1] < delays[2]


def test_row_is_abandoned_after_max_attempts(db_session) -> None:
    row = _enqueue(db_session)
    row.max_attempts = 3
    db_session.commit()
    for _ in range(3):
        outbox.mark_failed(db_session, row, "erreur")
    assert row.status == outbox.STATUS_ABANDONED
    assert row.next_retry_at is None


def test_mark_sent_clears_the_error_state(db_session) -> None:
    row = _enqueue(db_session)
    outbox.mark_failed(db_session, row, "erreur passagere")
    outbox.mark_sent(db_session, row)
    assert row.status == outbox.STATUS_SENT
    assert row.sent_at is not None
    assert row.last_error is None


def test_reset_for_retry_restores_a_clean_state(db_session) -> None:
    """Relance manuelle depuis l'interface comptable."""
    row = _enqueue(db_session)
    row.max_attempts = 2
    db_session.commit()
    outbox.mark_failed(db_session, row, "e")
    outbox.mark_failed(db_session, row, "e")
    assert row.status == outbox.STATUS_ABANDONED

    outbox.reset_for_retry(db_session, row, triggered_by=42)
    assert row.status == outbox.STATUS_PENDING
    assert row.attempts == 0
    assert row.triggered_by == 42


# ---- Livraison --------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_fails_when_an_attachment_is_missing(
    db_session, tmp_path: Path
) -> None:
    """Une piece jointe disparue ne doit pas produire un envoi vide."""
    row = _enqueue(db_session, attachments=[tmp_path / "absent.pdf"])
    delivered = await outbox._deliver(db_session, row)
    assert delivered is False
    assert row.status == outbox.STATUS_FAILED
    assert "introuvable" in (row.last_error or "").lower()


@pytest.mark.asyncio
async def test_delivery_without_recipient_does_not_consume_an_attempt(
    db_session, monkeypatch
) -> None:
    """Sinon la ligne serait abandonnee avant meme que l'adresse soit connue.

    ``compta_email_raw`` est vide de force : la livraison relit desormais la
    configuration, et l'environnement de test en porte une valeur valide.
    """
    monkeypatch.setattr(outbox.settings, "compta_email_raw", "")
    row = _enqueue(db_session, recipients=[])
    delivered = await outbox._deliver(db_session, row)
    assert delivered is False
    assert row.status == outbox.STATUS_PENDING
    assert row.attempts == 0


# ---- Consultation -----------------------------------------------------------


def test_latest_for_entity_returns_the_most_recent(db_session) -> None:
    _enqueue(db_session, entity_id=77, subject="premier")
    second = _enqueue(db_session, entity_id=77, subject="second")
    found = outbox.latest_for_entity(db_session, "invoice", 77)
    assert found is not None and found.id == second.id


def test_list_emails_filters_by_status(db_session) -> None:
    sent = _enqueue(db_session, entity_id=91)
    outbox.mark_sent(db_session, sent)
    _enqueue(db_session, entity_id=92)

    pendings = outbox.list_emails(db_session, status=outbox.STATUS_PENDING)
    assert all(r.status == outbox.STATUS_PENDING for r in pendings)
    assert sent.id not in {r.id for r in pendings}


# ---- Reprise apres configuration de COMPTA_EMAIL -----------------------------


@pytest.mark.asyncio
async def test_a_queued_mail_leaves_once_the_address_is_configured(
    db_session, monkeypatch
) -> None:
    """La promesse faite a la mise en file doit etre tenue.

    Une ligne creee sans COMPTA_EMAIL fige `recipients` a `[]`. Sans relecture
    de la configuration au moment de l'envoi, elle restait en attente pour
    toujours : renseigner l'adresse ne changeait rien, et les notes de frais
    deposees entre-temps n'atteignaient jamais le comptable.
    """
    row = _enqueue(db_session, recipients=[])
    assert json.loads(row.recipients) == []

    envoyes: list[tuple[str, list[str]]] = []

    async def _faux_envoi(subject, body, recipients, **kwargs):
        envoyes.append((subject, list(recipients)))

    monkeypatch.setattr(outbox.email_service, "_send_raw", _faux_envoi)
    monkeypatch.setattr(
        outbox.settings, "compta_email_raw", "comptabilite@lekouttab.fr"
    )

    assert await outbox._deliver(db_session, row) is True

    assert envoyes and envoyes[0][1] == ["comptabilite@lekouttab.fr"]
    assert row.status == outbox.STATUS_SENT
    # La ligne porte desormais le destinataire : la reprise est tracable.
    assert json.loads(row.recipients) == ["comptabilite@lekouttab.fr"]
    assert row.last_error is None


