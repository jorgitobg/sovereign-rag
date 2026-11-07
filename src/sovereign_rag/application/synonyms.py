"""Small, explicit synonym table for administrative Spanish.

Hand-written and deliberately tiny: each group lists words that mean the same thing in a
public-employment notice. It is not a thesaurus and it does not guess; a word outside the table
is matched literally, as before. Keys and values are accent-folded singular forms.
"""

from __future__ import annotations

GROUPS: tuple[tuple[str, ...], ...] = (
    ("plaza", "puesto", "vacante"),
    ("solicitud", "instancia"),
    ("personarse", "comparecer"),
    ("plazo", "tiempo"),
)

CANONICAL: dict[str, str] = {word: group[0] for group in GROUPS for word in group}
ALTERNATIVES: dict[str, tuple[str, ...]] = {
    word: tuple(w for w in group if w != word) for group in GROUPS for word in group
}


def canonical(word: str) -> str:
    """The group's representative, or the word itself when it is not in the table."""
    return CANONICAL.get(word, word)


def alternatives(word: str) -> tuple[str, ...]:
    return ALTERNATIVES.get(word, ())
