"""Chiffrement au repos des champs sensibles.

Un seul usage aujourd'hui : ``Admins.rib``. C'est la donnee la plus sensible de
la base (cf. CLAUDE.md §4) et elle y etait ecrite en clair, protegee par les
seules permissions applicatives. Or ces permissions ne protegent rien contre ce
qui contourne l'application : un export de la base, une sauvegarde egaree, un
acces MySQL direct. Les coordonnees bancaires de tous les benevoles tenaient
dans un ``SELECT``.

**AES-256-GCM**, en mode authentifie : une valeur modifiee directement en base
est refusee au lieu de produire un faux RIB en silence.

Format stocke : ``gcm1:<base64(nonce || chiffre || tag)>``.

Le prefixe porte la version du schema de chiffrement. Il sert deux fois : il
permettra d'introduire un ``gcm2`` sans ambiguite, et il distingue surtout une
valeur chiffree d'un RIB en clair herite — la base de production en contient, et
les lire doit continuer de fonctionner apres le deploiement.

Pas de donnees associees (AAD) liant le chiffre a son proprietaire : le
``TypeDecorator`` qui appelle ces fonctions ne connait pas l'identifiant de la
ligne. Deplacer un RIB d'un compte a l'autre directement en base resterait donc
possible pour qui a deja les droits d'ecriture MySQL — un adversaire nettement
plus avance que celui vise ici, et qui pourrait de toute facon changer l'IBAN
affiche a la comptabilite.

**La cle est irremplacable** : la perdre rend les RIB definitivement illisibles.
Elle vit dans le ``.env`` du serveur, jamais dans le depot.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.logger import get_logger


logger = get_logger("crypto")


PREFIXE = "gcm1:"
_TAILLE_NONCE = 12  # 96 bits : la taille recommandee pour GCM.
_TAILLE_CLE = 32  # AES-256.
_NOM_VARIABLE = "RIB_ENCRYPTION_KEY"

_cle_cache: bytes | None = None


class CleAbsente(RuntimeError):
    """Cle de chiffrement absente ou inexploitable."""


class ErreurDechiffrement(RuntimeError):
    """Valeur chiffree illisible : cle differente, ou contenu altere."""


def generer_cle() -> str:
    """Fabrique une cle utilisable telle quelle dans le ``.env``."""
    return base64.urlsafe_b64encode(os.urandom(_TAILLE_CLE)).decode()


def reinitialiser_cle() -> None:
    """Oublie la cle memorisee (tests, et rotation sans redemarrage)."""
    global _cle_cache
    _cle_cache = None


def _valeur_brute() -> str:
    """Lit la cle configuree.

    ``os.environ`` d'abord : en production, ``env_file`` de Compose injecte le
    ``.env`` dans l'environnement du conteneur. En developpement, le ``.env``
    n'est lu que par pydantic-settings, d'ou le repli sur les reglages.
    """
    depuis_env = os.environ.get(_NOM_VARIABLE, "").strip()
    if depuis_env:
        return depuis_env
    try:
        from app.core.config import settings

        return (settings.rib_encryption_key or "").strip()
    except Exception:  # pragma: no cover - configuration inutilisable
        return ""


def _cle() -> bytes:
    global _cle_cache
    if _cle_cache is not None:
        return _cle_cache

    brute = _valeur_brute()
    if not brute:
        raise CleAbsente(
            f"{_NOM_VARIABLE} n'est pas definie : impossible de chiffrer le RIB. "
            "Generer une cle avec : "
            'python -c "from app.core.crypto import generer_cle; print(generer_cle())"'
        )

    try:
        cle = base64.urlsafe_b64decode(brute)
    except Exception as exc:  # noqa: BLE001 - binascii leve des types varies
        raise CleAbsente(f"{_NOM_VARIABLE} n'est pas un base64 valide.") from exc

    if len(cle) != _TAILLE_CLE:
        raise CleAbsente(
            f"{_NOM_VARIABLE} doit faire {_TAILLE_CLE} octets une fois decodee "
            f"(actuellement {len(cle)})."
        )

    _cle_cache = cle
    return cle


def cle_disponible() -> bool:
    """Dit si le chiffrement est operationnel, sans lever."""
    try:
        _cle()
    except CleAbsente:
        return False
    return True


def est_chiffre(valeur: str) -> bool:
    return valeur.startswith(PREFIXE)


def chiffrer(valeur: str | None) -> str | None:
    """Chiffre une valeur. ``None`` et chaine vide traversent inchanges.

    Une valeur deja chiffree est rendue telle quelle : re-chiffrer a chaque
    ecriture ferait grossir la donnee sans rien apporter.
    """
    if valeur is None or valeur == "":
        return valeur
    if est_chiffre(valeur):
        return valeur

    nonce = os.urandom(_TAILLE_NONCE)
    chiffre = AESGCM(_cle()).encrypt(nonce, valeur.encode("utf-8"), None)
    return PREFIXE + base64.urlsafe_b64encode(nonce + chiffre).decode()


def dechiffrer(valeur: str | None) -> str | None:
    """Dechiffre une valeur.

    Une valeur sans prefixe est un RIB en clair herite de la version
    precedente : on la rend telle quelle. Sans cela, toute la page des notes de
    frais tomberait au premier deploiement, avant meme qu'un seul RIB ait ete
    converti.
    """
    if valeur is None or valeur == "":
        return valeur
    if not est_chiffre(valeur):
        return valeur

    try:
        brut = base64.urlsafe_b64decode(valeur[len(PREFIXE) :])
        nonce, chiffre = brut[:_TAILLE_NONCE], brut[_TAILLE_NONCE:]
        return AESGCM(_cle()).decrypt(nonce, chiffre, None).decode("utf-8")
    except InvalidTag as exc:
        raise ErreurDechiffrement(
            "RIB illisible : cle differente de celle du chiffrement, ou valeur "
            "modifiee en base."
        ) from exc
    except CleAbsente:
        raise
    except Exception as exc:  # noqa: BLE001 - base64 tronque, UTF-8 invalide...
        raise ErreurDechiffrement("RIB illisible : contenu chiffre invalide.") from exc


__all__ = [
    "CleAbsente",
    "ErreurDechiffrement",
    "chiffrer",
    "cle_disponible",
    "dechiffrer",
    "est_chiffre",
    "generer_cle",
    "reinitialiser_cle",
]
