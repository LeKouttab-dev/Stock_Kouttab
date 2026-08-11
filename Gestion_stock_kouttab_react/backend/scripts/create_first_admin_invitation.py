"""Amorce le tout premier compte Super Admin, sans mot de passe en dur.

Remplace ``seed_super_admin.py``, qui creait un compte ``admin`` / ``Admin1234!``
dont le mot de passe etait publie dans le depot, et qui n'avait aucun garde-fou
contre une execution accidentelle sur la base de production.

Le script ne cree aucun compte : il genere une invitation en base et affiche le
lien d'installation. L'operateur ouvre ce lien et choisit lui-meme son identifiant
et son mot de passe via le flux ``admin-setup`` habituel.

Usage :
    python scripts/create_first_admin_invitation.py <email>
    python scripts/create_first_admin_invitation.py <email> --force

``--force`` permet de regenerer une invitation alors qu'un Super Admin existe
deja (utile si le seul compte administrateur a ete perdu).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

# Permettre l'import du package "app" en lancant le script depuis backend/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.crud import invitation as invitation_crud  # noqa: E402
from app.db.models import Admin  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Adresse email du futur Super Admin")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Generer l'invitation meme si un Super Admin existe deja",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = (
            db.query(Admin)
            .filter(Admin.role == "Super Admin", Admin.validation_status == "active")
            .first()
        )
        if existing and not args.force:
            print(
                f"[ABANDON] Un Super Admin actif existe deja ('{existing.username}').\n"
                "          Les administrateurs suivants se creent depuis l'application\n"
                "          (Administration > Invitations). Utiliser --force uniquement\n"
                "          si l'acces a ce compte est definitivement perdu."
            )
            return 1

        invitation, token = invitation_crud.create_invitation(db, args.email)

        base = settings.frontend_url.rstrip("/")
        link = (
            f"{base}/admin-setup"
            f"?token={quote(token, safe='')}&email={quote(args.email, safe='')}"
        )
        print("[OK] Invitation creee.")
        print(f"     Email      : {args.email}")
        print(f"     Expire le  : {invitation.expires_at} (UTC)")
        print()
        print("     Ouvrir ce lien pour creer le compte Super Admin :")
        print(f"     {link}")
        print()
        print("     Ce lien est a usage unique et n'est affiche qu'une fois :")
        print("     seul son empreinte SHA256 est conservee en base.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
