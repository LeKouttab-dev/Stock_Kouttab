"""Traite la file des envois comptables. A lancer par le cron cPanel.

Exemple de configuration (cPanel > Cron Jobs, toutes les 10 minutes) :

    */10 * * * * cd /home/USER/stock.lekouttab.fr/backend && \
      /home/USER/virtualenv/stock.lekouttab.fr/3.11/bin/python \
      scripts/process_outbound_emails.py >> logs/outbox.log 2>&1

Le script sort toujours en code 0, meme si des envois echouent : un code
d'erreur ferait envoyer un mail d'alerte par cPanel a chaque execution, ce qui
noierait les vraies anomalies. Les echecs sont journalises et visibles dans
l'interface (Administration > Envois comptables).
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.logger import get_logger  # noqa: E402
from app.db.models import OutboundEmail  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import outbox  # noqa: E402


logger = get_logger("cron.outbox")


def cleanup(days: int) -> int:
    """Supprime les PDF des envois aboutis depuis plus de ``days`` jours.

    Sans cela, le disque mutualise se remplit : chaque justificatif existe en
    double (l'original dans uploads/, la copie nommee dans outbox/).
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    removed = 0
    db = SessionLocal()
    try:
        rows = (
            db.query(OutboundEmail)
            .filter(
                OutboundEmail.status == outbox.STATUS_SENT,
                OutboundEmail.sent_at.isnot(None),
                OutboundEmail.sent_at < cutoff,
            )
            .all()
        )
        for row in rows:
            directory = settings.outbox_path / row.entity_type / str(row.entity_id)
            if directory.exists():
                shutil.rmtree(directory, ignore_errors=True)
                removed += 1
    finally:
        db.close()
    if removed:
        logger.info("Nettoyage : %d repertoire(s) d'envoi supprime(s).", removed)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=20, help="Nombre maximal d'envois par execution"
    )
    parser.add_argument(
        "--cleanup-days",
        type=int,
        default=30,
        help="Supprimer les PDF des envois aboutis depuis N jours (0 = desactive)",
    )
    args = parser.parse_args()

    try:
        stats = asyncio.run(outbox.process_pending(limit=args.limit))
        logger.info(
            "File comptable traitee : %d envoye(s), %d en echec, %d ignore(s).",
            stats["sent"],
            stats["failed"],
            stats["skipped"],
        )
        if args.cleanup_days > 0:
            cleanup(args.cleanup_days)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Traitement de la file comptable interrompu : %s", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
