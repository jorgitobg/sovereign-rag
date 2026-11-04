from pathlib import Path

from sovereign_rag.adapters.boe_xml import parse_boe
from sovereign_rag.application.ingest import chunk_document, ingest_files
from sovereign_rag.domain.models import Document

BOE = Path(__file__).parent / "fixtures" / "boe"


def test_parse_boe_keeps_metadata() -> None:
    doc = parse_boe((BOE / "BOE-A-2026-23041.xml").read_bytes())
    assert doc.id == "BOE-A-2026-23041"
    assert "Torrox" in doc.title and doc.department == "Administración Local"
    assert doc.published is not None and doc.published.isoformat() == "2026-11-03"
    assert doc.url == "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-23041"
    assert any("Subalterno" in p for p in doc.paragraphs)


def test_parse_boe_normalises_non_breaking_spaces() -> None:
    xml = (
        "<documento><metadatos><identificador>X</identificador><titulo>Ley\u00a05</titulo>"
        "</metadatos><texto><p>a\u00a0b</p></texto></documento>"
    )
    doc = parse_boe(xml.encode())
    assert doc.title == "Ley 5" and doc.paragraphs == ("a b",)


def test_ingest_fixtures_yields_cited_chunks() -> None:
    chunks, issues = ingest_files(BOE.glob("*.xml"), parse_boe)
    assert not issues and len({c.doc_id for c in chunks}) == 11
    assert all(c.url.startswith("https://www.boe.es/") and c.title for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_unparsable_file_is_reported_and_skipped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_text("<x>", encoding="utf-8")
    nometa = tmp_path / "nometa.xml"
    nometa.write_text("<documento/>", encoding="utf-8")
    good = BOE / "BOE-A-2026-23041.xml"
    chunks, issues = ingest_files([bad, nometa, good, tmp_path / "missing.xml"], parse_boe)
    assert {i.ref for i in issues} == {"bad.xml", "nometa.xml", "missing.xml"}
    assert chunks


def test_paragraphs_in_a_chunk_stay_separated_by_newlines() -> None:
    doc = Document("d", "t", "dep", None, "u", ("uno sin punto", "dos"))
    assert chunk_document(doc)[0].text == "uno sin punto\ndos"


def test_chunking_respects_size_and_splits_long_paragraphs() -> None:
    doc = Document("d", "t", "dep", None, "u", ("a " * 50, "", "b " * 400))
    chunks = chunk_document(doc, max_chars=200)
    assert all(len(c.text) <= 200 for c in chunks)
    assert [c.id for c in chunks] == [f"d#{i}" for i in range(len(chunks))]
    assert len(chunks) > 3
