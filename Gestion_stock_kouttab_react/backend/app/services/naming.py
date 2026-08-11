"""Nomenclature des fichiers envoyes au service comptable.

Format retenu avec le client : ``{Pole}_{Evenement}_{AAAA-MM-JJ}.pdf``

Deux conventions de separateur, volontairement distinctes :
- ``_`` separe les composants,
- ``-`` remplace tout caractere invalide *a l'interieur* d'un composant.

Le comptable peut ainsi re-decouper un nom par ``split("_")`` sans ambiguite,
ce qui serait impossible si les deux roles se confondaient.

La sortie est garantie **ASCII pur** : aucun encodage RFC 2231 n'est necessaire
dans l'en-tete ``Content-Disposition``, donc aucun client de messagerie ne
deforme le nom de la piece jointe.

Module volontairement pur : aucune I/O, aucun acces base, aucune dependance a
FastAPI. Il est donc testable exhaustivement (cf. ``tests/unit/test_naming.py``)
et duplique a l'identique cote frontend (``src/lib/naming.ts``) pour afficher au
deposant le nom exact qui sera envoye.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from datetime import date


MAX_COMPONENT_LEN = 40
MAX_STEM_LEN = 120
MISSING = "NC"
DATE_FORMAT = "%Y-%m-%d"

# Caracteres que la decomposition NFKD ne separe pas : ils disparaitraient
# purement et simplement a l'etape ASCII sans ce passage prealable.
_EXPLICIT_REPLACEMENTS = {
    "œ": "oe",
    "Œ": "OE",
    "æ": "ae",
    "Æ": "AE",
    "ß": "ss",
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "&": "et",
    "@": "at",
    "°": "deg",
    "'": "",
    "'": "",
    "`": "",
    '"': "",
    "«": "",
    "»": "",
}

# Noms reserves par Windows : un fichier « CON.pdf » est indecompressable et
# provoque des erreurs opaques cote destinataire.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")
_MULTI_DASH = re.compile(r"-{2,}")


def slugify_component(value: str | None, *, max_len: int = MAX_COMPONENT_LEN) -> str:
    """Reduit un libelle libre a un composant de nom de fichier sur.

    Retourne ``MISSING`` si rien d'exploitable ne subsiste — jamais une chaine
    vide, qui produirait un ``__`` cassant le decoupage du nom.
    """
    if value is None:
        return MISSING

    text = str(value)
    for source, target in _EXPLICIT_REPLACEMENTS.items():
        text = text.replace(source, target)

    # Decomposition puis suppression des diacritiques : e -> e, c -> c.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # Filet de securite pour les alphabets non translitterables (cyrillique,
    # arabe, CJK) : mieux vaut les perdre que produire des octets invalides.
    text = text.encode("ascii", "ignore").decode("ascii")

    # Neutralise d'un coup les interdits Windows (< > : " / \ | ? *), les
    # caracteres de controle, les espaces et les points.
    text = _NON_ALNUM.sub("-", text)
    text = _MULTI_DASH.sub("-", text).strip("-")

    if not text:
        return MISSING

    if len(text) > max_len:
        text = text[:max_len]
        # Coupe sur une frontiere de mot plutot qu'au milieu, si possible.
        if "-" in text[1:]:
            text = text[: text.rindex("-")]
        text = text.strip("-")

    if not text:
        return MISSING
    if text.upper() in _WINDOWS_RESERVED:
        text = f"_{text}"
    return text


def format_date_component(value: date | None) -> str:
    return value.strftime(DATE_FORMAT) if value is not None else MISSING


def build_attachment_stem(
    components: Sequence[str | None],
    date_value: date | None,
) -> str:
    """Assemble le nom (sans extension) a partir des composants et de la date."""
    parts = [slugify_component(c) for c in components]
    parts.append(format_date_component(date_value))
    stem = "_".join(parts)
    if len(stem) > MAX_STEM_LEN:
        stem = stem[:MAX_STEM_LEN].strip("-_")
    return stem


def build_attachment_filename(
    components: Sequence[str | None],
    date_value: date | None,
    *,
    extension: str = "pdf",
) -> str:
    ext = extension.lstrip(".").lower() or "pdf"
    return f"{build_attachment_stem(components, date_value)}.{ext}"


def deduplicate_filenames(names: Sequence[str]) -> list[str]:
    """Rend uniques des noms identiques en suffixant ``-2``, ``-3``...

    Les justificatifs d'un meme depot partagent pole, evenement et date : sans
    cette passe, les N pieces jointes porteraient le meme nom et les clients de
    messagerie en ecraseraient certaines.

    Pas de suffixe entre parentheses facon « (1) » : les espaces et parentheses
    survivent mal aux anciennes passerelles SMTP.
    """
    seen: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        stem, _, ext = name.rpartition(".")
        if not stem:  # nom sans extension
            stem, ext = name, ""
        key = name.lower()
        count = seen.get(key, 0) + 1
        seen[key] = count
        if count == 1:
            result.append(name)
            continue
        suffix = f"-{count}"
        # Laisse la place au suffixe, sinon la troncature le ferait sauter et la
        # collision reapparaitrait silencieusement.
        if len(stem) + len(suffix) > MAX_STEM_LEN:
            stem = stem[: MAX_STEM_LEN - len(suffix)].strip("-_")
        result.append(f"{stem}{suffix}.{ext}" if ext else f"{stem}{suffix}")
    return result
