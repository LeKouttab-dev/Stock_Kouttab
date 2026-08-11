"""Nomenclature des pieces envoyees au comptable.

Table de cas volontairement exhaustive : chaque ligne correspond a une facon
concrete de casser un nom de fichier chez le destinataire. Le fichier jumeau
``frontend/src/lib/__tests__/naming.test.ts`` rejoue la meme table, ce qui
garantit que l'apercu affiche au deposant correspond au fichier reellement
envoye.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.naming import (
    MAX_COMPONENT_LEN,
    MAX_STEM_LEN,
    MISSING,
    build_attachment_filename,
    deduplicate_filenames,
    slugify_component,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Accents : cas nominal francais.
        ("Pôle événementiel", "Pole-evenementiel"),
        ("Institut", "Institut"),
        ("Local", "Local"),
        # Ligatures et symboles que NFKD ne decompose pas.
        ("Cœur & Âme", "Coeur-et-Ame"),
        ("Tarif 50€", "Tarif-50EUR"),
        ("Fête de l'été", "Fete-de-lete"),
        # Caracteres interdits par Windows.
        ('Gala: 50% / "Été"', "Gala-50-Ete"),
        ("a<b>c:d|e?f*g", "a-b-c-d-e-f-g"),
        ("chemin/../../etc/passwd", "chemin-etc-passwd"),
        # Separateurs multiples et bordures.
        ("a///b\\\\c", "a-b-c"),
        ("  -Gala-  ", "Gala"),
        ("---", MISSING),
        # Caracteres de controle.
        ("a\x00b\x1fc", "a-b-c"),
        ("ligne\nsuivante", "ligne-suivante"),
        # Noms reserves Windows.
        ("CON", "_CON"),
        ("com1", "_com1"),
        ("console", "console"),  # ne commence pas par un nom reserve exact
        # Valeurs vides ou non exploitables.
        ("", MISSING),
        (None, MISSING),
        ("###", MISSING),
        ("Мероприятие", MISSING),  # cyrillique : non translitterable
        ("日本語", MISSING),
    ],
)
def test_slugify_component(raw: str | None, expected: str) -> None:
    assert slugify_component(raw) == expected


def test_slugify_output_is_always_pure_ascii() -> None:
    """Garantit qu'aucun encodage RFC 2231 n'est necessaire dans les en-tetes."""
    for raw in ("Pôle événementiel", "Cœur", "日本語", "Ünïcödé", "a b"):
        result = slugify_component(raw)
        result.encode("ascii")  # leve si non-ASCII
        assert result


def test_slugify_truncates_on_a_word_boundary() -> None:
    raw = "Gala-de-bienfaisance-annuel-de-l-association-Le-Kouttab-edition-2026"
    result = slugify_component(raw)
    assert len(result) <= MAX_COMPONENT_LEN
    assert not result.endswith("-")
    # La coupe tombe entre deux mots, pas au milieu de l'un d'eux.
    assert raw.startswith(result)


def test_slugify_handles_a_long_word_without_separator() -> None:
    result = slugify_component("A" * 200)
    assert len(result) <= MAX_COMPONENT_LEN
    assert result == "A" * MAX_COMPONENT_LEN


# ---- Nom complet ------------------------------------------------------------


def test_build_filename_nominal_case() -> None:
    name = build_attachment_filename(
        ["Pôle événementiel", "Gala d'été 2026"], date(2026, 3, 14)
    )
    assert name == "Pole-evenementiel_Gala-dete-2026_2026-03-14.pdf"


def test_build_filename_with_missing_components() -> None:
    name = build_attachment_filename([None, ""], None)
    assert name == f"{MISSING}_{MISSING}_{MISSING}.pdf"
    # Aucun separateur double, qui casserait le decoupage par split('_').
    assert "__" not in name


def test_build_filename_respects_the_requested_extension() -> None:
    assert build_attachment_filename(["Local"], date(2026, 1, 2), extension=".JPG").endswith(
        ".jpg"
    )


def test_build_filename_stays_within_the_length_budget() -> None:
    name = build_attachment_filename(["A" * 300, "B" * 300], date(2026, 3, 14))
    assert len(name) <= MAX_STEM_LEN + len(".pdf")


def test_components_remain_separable() -> None:
    """Le comptable doit pouvoir re-decouper le nom de maniere fiable."""
    name = build_attachment_filename(
        ["Pôle institut", "Sortie au musée"], date(2026, 5, 9)
    )
    stem = name.rsplit(".", 1)[0]
    pole, evenement, jour = stem.split("_")
    assert pole == "Pole-institut"
    assert evenement == "Sortie-au-musee"
    assert jour == "2026-05-09"


# ---- Deduplication ----------------------------------------------------------


def test_deduplicate_suffixes_repeated_names() -> None:
    names = ["Local_Gala_2026-03-14.pdf"] * 3
    assert deduplicate_filenames(names) == [
        "Local_Gala_2026-03-14.pdf",
        "Local_Gala_2026-03-14-2.pdf",
        "Local_Gala_2026-03-14-3.pdf",
    ]


def test_deduplicate_leaves_distinct_names_untouched() -> None:
    names = ["a.pdf", "b.pdf", "c.pdf"]
    assert deduplicate_filenames(names) == names


def test_deduplicate_is_case_insensitive() -> None:
    """Les systemes de fichiers Windows et macOS ignorent la casse."""
    result = deduplicate_filenames(["Facture.pdf", "facture.pdf"])
    assert result[1] != result[0]
    assert len({n.lower() for n in result}) == 2


def test_deduplicate_keeps_names_unique_at_maximum_length() -> None:
    """La troncature ne doit pas faire disparaitre le suffixe."""
    long_name = "A" * MAX_STEM_LEN + ".pdf"
    result = deduplicate_filenames([long_name] * 3)
    assert len({n.lower() for n in result}) == 3
    for name in result:
        assert len(name.rsplit(".", 1)[0]) <= MAX_STEM_LEN


def test_deduplicate_handles_names_without_extension() -> None:
    assert deduplicate_filenames(["piece", "piece"]) == ["piece", "piece-2"]
