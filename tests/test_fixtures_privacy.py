"""Guards for the public corpus: provenance is exact and no personal identifiers appear."""

import re
from pathlib import Path

BOE = Path(__file__).parent / "fixtures" / "boe"
PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "dni_nie": re.compile(r"\b[XYZ]?\d{7,8}-?[A-Z]\b"),
    "phone": re.compile(r"(?<!\d)(?:\+34)?[ .]?[6-9]\d{2}[ .]?\d{3}[ .]?\d{3}(?!\d)"),
    "iban": re.compile(r"\bES\d{2}[ ]?\d{4}"),
}


def test_no_personal_identifiers_in_fixtures() -> None:
    for path in BOE.glob("*.xml"):
        text = path.read_text(encoding="utf-8")
        for name, pat in PATTERNS.items():
            assert not pat.search(text), f"{path.name}: {name}"


def test_sources_md_lists_exactly_the_committed_fixtures() -> None:
    listed = set(re.findall(r"BOE-A-\d{4}-\d+", (BOE / "SOURCES.md").read_text(encoding="utf-8")))
    assert listed == {p.stem for p in BOE.glob("*.xml")}


def test_fixtures_contain_no_candidate_lists() -> None:
    # Allowed content is institutional; admitted/excluded or candidate lists are not.
    for path in BOE.glob("*.xml"):
        text = path.read_text(encoding="utf-8").lower()
        for banned in ("lista de admitidos", "relación de aspirantes", "lista de excluidos"):
            assert banned not in text, path.name
