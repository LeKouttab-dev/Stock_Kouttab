"""
TEMPORAIRE - Bootstrap rapide d'un Super Admin pour tester l'app en local.

Usage :
    cd backend
    python scripts/seed_super_admin.py

Crée (si absent) un compte Super Admin avec les credentials par defaut :
    username = admin
    password = Admin1234!
    email    = admin@lekouttab.fr
    role     = Super Admin
    status   = active

A REMPLACER PAR L'OPTION A (script d'invitation) avant la mise en production.
Voir CLAUDE.md section "Bootstrap initial".

Variables d'environnement supportees pour override :
    SEED_USERNAME (defaut "admin")
    SEED_PASSWORD (defaut "Admin1234!")
    SEED_EMAIL    (defaut "admin@lekouttab.fr")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Permettre l'import du package "app" en lancant le script depuis backend/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import Admin  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402


DEFAULT_USERNAME = os.environ.get("SEED_USERNAME", "admin")
DEFAULT_PASSWORD = os.environ.get("SEED_PASSWORD", "Admin1234!")
DEFAULT_EMAIL = os.environ.get("SEED_EMAIL", "admin@lekouttab.fr")


def seed() -> int:
    # En SQLite local, on cree les tables a la volee (utile tant qu'on n'a
    # pas branche Alembic ou MySQL). Pour MySQL prod, prefere `alembic upgrade head`.
    print("[INFO] Verification / creation des tables...")
    Base.metadata.create_all(bind=engine)

    # Cree le dossier data/ si on est en SQLite et qu'il manque
    db_url = str(engine.url)
    if db_url.startswith("sqlite") and "/" in db_url:
        sqlite_path = Path(db_url.split("///", 1)[-1])
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        existing = db.query(Admin).filter(Admin.username == DEFAULT_USERNAME).first()
        if existing:
            print(f"[OK] Un utilisateur '{DEFAULT_USERNAME}' existe deja (id={existing.id}).")
            print(f"     role={existing.role}, status={existing.validation_status}")
            print()
            print("     Si tu veux reinitialiser :")
            print(f"     1) supprime-le en SQL : DELETE FROM Admins WHERE username='{DEFAULT_USERNAME}';")
            print("     2) relance ce script.")
            return 0

        admin = Admin(
            username=DEFAULT_USERNAME,
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="Super Admin",
            validation_status="active",
            nom="Admin",
            prenom="System",
            email=DEFAULT_EMAIL,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("=" * 60)
        print(" SUPER ADMIN CREE AVEC SUCCES")
        print("=" * 60)
        print(f"  username : {DEFAULT_USERNAME}")
        print(f"  password : {DEFAULT_PASSWORD}")
        print(f"  email    : {DEFAULT_EMAIL}")
        print(f"  role     : Super Admin")
        print(f"  id       : {admin.id}")
        print("=" * 60)
        print()
        print(" Connecte-toi sur http://localhost:5173 avec ces identifiants.")
        print(" CHANGE LE MOT DE PASSE depuis l'app avant la mise en production.")
        print()
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[ERREUR] Impossible de creer le Super Admin : {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(seed())
