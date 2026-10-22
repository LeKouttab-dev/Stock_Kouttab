"""Transmet au tresorier les RIB encore en base, puis les efface.

A lancer UNE fois, a la main, depuis le VPS, une fois `RIB_DESTINATAIRE_EMAIL`
pose dans le `.env` :

    cd /opt/projets/kouttab-stock
    sudo docker compose exec api python scripts/transmettre_et_purger_rib.py
    sudo docker compose exec api python scripts/transmettre_et_purger_rib.py --envoyer

**Rien ne part ni ne s'efface sans `--envoyer`.** Sans ce drapeau, le script
affiche qui serait transmis.

Pour chaque compte qui a encore un IBAN ou un releve en base : un courriel au
tresorier (IBAN et PDF), PUIS l'effacement, compte par compte. Un echec d'envoi
laisse le compte tel quel et passe au suivant — relancer le script reprend la
ou il s'est arrete, puisqu'un compte purge n'a plus rien a transmettre.

``--purger-seulement`` efface tout sans rien envoyer : le repli, si le
tresorier a deja tout recupere par ailleurs.

Pourquoi pas une migration : une migration ne doit pas envoyer de courriels, et
purger avant d'avoir transmis ferait perdre les RIB des remboursements en
attente.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Admin
from app.db.session import SessionLocal
from app.services import rib as rib_service

logger = get_logger("purge_rib")


def comptes_avec_rib(db: Session) -> list[Admin]:
    stmt = select(Admin).where(
        or_(Admin.rib.is_not(None), Admin.rib_document_type.is_not(None))
    )
    return list(db.execute(stmt).scalars().all())


async def traiter(db: Session, *, envoyer: bool, purger_seulement: bool) -> tuple[int, int]:
    """Rend (comptes traites, echecs)."""
    if envoyer and not purger_seulement:
        rib_service.destinataire()  # leve tout de suite si rien n'est configure
    traites = echecs = 0
    for compte in comptes_avec_rib(db):
        iban = rib_service.normaliser_iban(compte.rib) or None
        pdf = compte.rib_document
        print(
            f"  {compte.username:<20} IBAN {'oui' if iban else 'non'}, "
            f"releve {'oui' if pdf else 'non'}"
        )
        if not envoyer:
            continue
        if not purger_seulement:
            try:
                await rib_service.envoyer_au_tresorier(
                    compte, iban=iban, pdf=pdf, origine="reprise"
                )
            except AppException as exc:
                # Le compte garde son RIB : rien n'est efface de ce qui n'a pas
                # ete recu.
                logger.error("RIB de %s non transmis : %s", compte.username, exc)
                echecs += 1
                continue
        rib_service.marquer_transmis(compte, iban)
        db.commit()
        traites += 1
    return traites, echecs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--envoyer", action="store_true", help="Transmettre et effacer")
    parser.add_argument(
        "--purger-seulement", action="store_true", help="Effacer sans rien envoyer"
    )
    args = parser.parse_args()
    if args.purger_seulement and not args.envoyer:
        parser.error("--purger-seulement s'utilise avec --envoyer.")

    with SessionLocal() as db:
        traites, echecs = asyncio.run(
            traiter(db, envoyer=args.envoyer, purger_seulement=args.purger_seulement)
        )
    if not args.envoyer:
        print("A sec : rien n'a ete envoye ni efface. Relancer avec --envoyer.")
    else:
        print(f"{traites} RIB transmis et effaces, {echecs} echec(s).")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
