"""Passage signé depuis gestion.lekouttab.fr.

Le jeton reçu atteste une **identité** (l'email vérifié par l'outil de
gestion), jamais un droit : un compte existant garde son rôle, un compte créé
à la volée naît ``BenevoleFrais`` — confiné aux notes de frais.

Trois défenses, dans l'ordre :
1. la signature (secret partagé **dédié**, jamais ``JWT_SECRET_KEY``), avec
   audience, émetteur, type et durée de vie bornée — un access token de
   gestion, même volé, n'est pas échangeable ;
2. l'usage unique : le ``jti`` est consommé par une **insertion** sous
   contrainte unique (``SsoEchanges``) — atomique, partagé entre workers,
   survivant aux redémarrages, contrairement à un set en mémoire ;
3. le rapprochement par email refuse l'ambiguïté : ``Admins.email`` n'étant
   pas unique, deux comptes sur la même adresse font échouer le passage
   plutôt que de deviner lequel ouvrir.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import ExpiredSignatureError, JWTError
from jose import jwt as jose_jwt
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.crud.user import get_user_by_username
from app.core.security import hash_jti, hash_password
from app.db.models import Admin, SsoEchange


# Marge sur la borne de durée de vie : deux horloges ne sont jamais exactement
# d'accord, et refuser un jeton honnête pour cinq secondes de dérive serait
# une panne incompréhensible depuis l'autre application.
_MARGE_HORLOGE_S = 10


def verifier_jeton(
    token: str, secret: str, *, typ_attendu: str = "sso", exiger_jti: bool = True
) -> dict[str, Any]:
    """Décode et contrôle un jeton de passage. Lève ``AppException`` sinon."""
    try:
        charge = jose_jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=settings.sso_audience,
            issuer=settings.sso_issuer,
        )
    except ExpiredSignatureError as exc:
        raise AppException(ErrorCode.TOKEN_EXPIRED) from exc
    except JWTError as exc:
        raise AppException(ErrorCode.TOKEN_INVALID) from exc

    if charge.get("typ") != typ_attendu:
        raise AppException(ErrorCode.TOKEN_INVALID, detail="Jeton de mauvais type.")

    # Un émetteur mal configuré qui signerait des jetons d'une heure ne doit
    # pas élargir la fenêtre de rejeu : la borne est tenue ici aussi.
    iat, exp = charge.get("iat"), charge.get("exp")
    if not isinstance(iat, int) or not isinstance(exp, int) or (
        exp - iat > settings.sso_max_age_seconds + _MARGE_HORLOGE_S
    ):
        raise AppException(ErrorCode.TOKEN_INVALID, detail="Durée de vie du jeton invalide.")

    email = (charge.get("email") or "").strip().lower()
    jti = charge.get("jti")
    if not email or "@" not in email or (exiger_jti and not jti):
        raise AppException(ErrorCode.TOKEN_INVALID, detail="Jeton incomplet.")

    return charge


def consommer_jti(db: Session, jti: str, expire_a: datetime) -> None:
    """Marque le jeton comme utilisé — l'insertion EST le verrou anti-rejeu."""
    # Ménage au passage : les lignes largement expirées ne servent plus à rien.
    db.execute(
        delete(SsoEchange).where(
            SsoEchange.expires_at < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        )
    )
    db.add(SsoEchange(jti_hash=hash_jti(str(jti)), expires_at=expire_a))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppException(ErrorCode.TOKEN_INVALID, detail="Jeton déjà utilisé.") from exc


def _username_libre(db: Session, email: str) -> str:
    """Un identifiant valide (``^[A-Za-z0-9_]{3,20}$``) et libre, dérivé de l'email."""
    base = re.sub(r"[^A-Za-z0-9_]", "", email.split("@")[0])[:16]
    if len(base) < 3:
        base = (base + "frais")[:16]
    candidat, suffixe = base, 2
    while get_user_by_username(db, candidat) is not None:
        queue = str(suffixe)
        candidat = f"{base[: 20 - len(queue)]}{queue}"
        suffixe += 1
    return candidat


def retrouver_ou_creer(db: Session, *, email: str, prenom: str | None, nom: str | None) -> Admin:
    """Le compte portant cet email — ou un compte ``BenevoleFrais`` neuf.

    Le mot de passe du compte créé est aléatoire et n'est communiqué à
    personne : le passage signé est sa seule porte. Le flux de
    réinitialisation existant pourra en donner un plus tard si besoin.
    """
    comptes = list(
        db.execute(
            select(Admin).where(func.lower(Admin.email) == email.lower())
        ).scalars().all()
    )
    if len(comptes) > 1:
        raise AppException(ErrorCode.SSO_EMAIL_AMBIGU)
    if comptes:
        return comptes[0]

    compte = Admin(
        username=_username_libre(db, email),
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role="BenevoleFrais",
        validation_status="active",
        email=email,
        prenom=prenom or None,
        nom=nom or None,
    )
    db.add(compte)
    db.commit()
    db.refresh(compte)
    return compte
