"""Le RIB d'un benevole : transmis au tresorier, jamais conserve.

Jusqu'au 22/10/2026, l'IBAN (chiffre) et le document (en clair) vivaient dans
`Admins`. Une donnee bancaire en base, c'est une donnee bancaire dans chaque
sauvegarde, chaque export, et a la portee de quiconque lit la base — y compris
par une autre application qui y aurait acces. Or l'application n'en a pas
besoin : c'est la banque qui paie, et le tresorier y enregistre le
beneficiaire une fois pour toutes.

Le RIB part donc par courriel au tresorier, **une fois**, et seules restent en
base la date de transmission et la fin de l'IBAN.

Trois regles, qui sont tout l'interet du module :

- **Pas de file d'envoi** (`outbox`) : elle garde le corps en base et les
  pieces sur disque pour pouvoir reessayer. C'est precisement ce qu'on veut
  eviter. L'envoi est direct ; s'il echoue, le benevole redepose.
- **Le PDF ne touche le disque que le temps de l'envoi**, dans un dossier
  temporaire prive supprime aussitot : fastapi-mail ne joint qu'un chemin.
- **La base n'est ecrite qu'apres un envoi reussi.** L'inverse dirait « RIB
  transmis » pour un RIB que personne n'a recu.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from app.core.config import settings
from app.core.errors import ErrorCode
from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.db.models import Admin
from app.services import email, email_layout
from app.utils.helpers import utcnow

logger = get_logger("rib")


def normaliser_iban(brut: str | None) -> str:
    """`fr76 3000 ...` -> `FR763000...` : sans espaces, en majuscules."""
    return re.sub(r"\s+", "", brut or "").upper()


def iban_valide(iban: str) -> bool:
    """Controle de la cle (ISO 13616, modulo 97).

    Il n'y avait aucune validation : un IBAN mal recopie arrivait jusqu'au
    virement, et c'est la banque qui le refusait, des semaines plus tard.
    """
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    reordonne = iban[4:] + iban[:4]
    chiffres = "".join(str(int(c, 36)) for c in reordonne)
    return int(chiffres) % 97 == 1


def iban_affiche(iban: str) -> str:
    """Par groupes de quatre, comme sur un releve : plus facile a recopier."""
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))


def destinataire() -> str:
    adresse = settings.rib_destinataire_email.strip()
    if not adresse:
        raise AppException(
            ErrorCode.SERVICE_UNAVAILABLE,
            detail=(
                "L'envoi des RIB n'est pas configure (RIB_DESTINATAIRE_EMAIL). "
                "Prevenez l'administrateur."
            ),
        )
    return adresse


def _nom_de(user: Admin) -> str:
    return user.full_name or user.username


def _nom_de_fichier(user: Admin) -> str:
    nom = re.sub(r"[^\w .-]", "", _nom_de(user), flags=re.UNICODE).strip() or "benevole"
    return f"RIB - {nom}.pdf"


async def envoyer_au_tresorier(
    user: Admin, *, iban: str | None, pdf: bytes | None, origine: str = "depot"
) -> None:
    """Envoie le RIB au tresorier. Leve si l'envoi echoue ; n'ecrit rien en base."""
    lignes = [
        email_layout.entete(),
        "",
        f"{_nom_de(user)} vous transmet son RIB"
        + (" (reprise des RIB enregistres dans l'application)." if origine == "reprise" else "."),
        "",
        f"Benevole : {_nom_de(user)}",
        f"Courriel : {user.email or '-'}",
        f"IBAN : {iban_affiche(iban) if iban else 'non renseigne'}",
        f"Releve en piece jointe : {'oui' if pdf else 'non'}",
        "",
        "Ce RIB n'est PAS conserve dans l'application. Enregistrez le beneficiaire",
        "dans l'espace bancaire de l'association, puis supprimez ce courriel :",
        "une boite qui garde les RIB devient a son tour une base de RIB.",
        "",
        email_layout.SIGNATURE,
    ]
    sujet = f"RIB de {_nom_de(user)}"
    with tempfile.TemporaryDirectory(prefix="rib-") as dossier:
        pieces: list[Path] = []
        if pdf:
            chemin = Path(dossier) / _nom_de_fichier(user)
            chemin.write_bytes(pdf)
            chemin.chmod(0o600)
            pieces.append(chemin)
        await email._send_raw(sujet, "\n".join(lignes), [destinataire()], attachments=pieces)


def marquer_transmis(user: Admin, iban: str | None) -> None:
    """Ce qui reste en base d'un RIB transmis. Le RIB lui-meme : rien."""
    user.rib_transmis_le = utcnow().replace(tzinfo=None)
    user.rib_iban_fin = iban[-4:] if iban else None
    user.rib = None
    user.rib_document = None
    user.rib_document_nom = None
    user.rib_document_type = None


async def confirmer_au_benevole(user: Admin) -> None:
    """Accuse de reception, sans le moindre chiffre bancaire. Best-effort."""
    if not user.email:
        return
    corps = (
        f"{email_layout.entete(user.prenom)}\n\n"
        "Votre RIB a bien ete transmis au tresorier de l'association. Il n'est pas "
        "conserve dans l'application.\n\n"
        "Vous pouvez desormais deposer vos notes de frais. Si vous changez de "
        "compte bancaire, transmettez simplement votre nouveau RIB depuis votre profil.\n\n"
        f"{email_layout.SIGNATURE}"
    )
    await email._send("Votre RIB a bien ete transmis", corps, [user.email])


__all__ = [
    "confirmer_au_benevole",
    "destinataire",
    "envoyer_au_tresorier",
    "iban_affiche",
    "iban_valide",
    "marquer_transmis",
    "normaliser_iban",
]
