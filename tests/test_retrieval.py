from pathlib import Path

from sovereign_rag.adapters.boe_xml import parse_boe
from sovereign_rag.adapters.fts5 import SqliteFtsRetriever, fold, query_terms
from sovereign_rag.adapters.hashing import HashingEmbedder
from sovereign_rag.application.ingest import ingest_files
from sovereign_rag.domain.models import Chunk
from sovereign_rag.domain.ports import Embedder, Retriever


def dot(u: list[float], v: list[float]) -> float:
    return sum(x * y for x, y in zip(u, v, strict=True))


BOE = Path(__file__).parent / "fixtures" / "boe"


def build() -> SqliteFtsRetriever:
    chunks, _ = ingest_files(BOE.glob("*.xml"), parse_boe)
    r = SqliteFtsRetriever()
    r.index(chunks)
    return r


def test_fold_and_terms_drop_accents_and_stopwords() -> None:
    assert fold("Resolución") == "resolucion"
    assert query_terms("La convocatoria de plazas del Ayuntamiento") == [
        "convocatoria",
        "plazas",
        "ayuntamiento",
    ]


def test_search_finds_local_government_call_first() -> None:
    r: Retriever = build()
    hits = r.search("convocatoria plazas ayuntamiento", k=4)
    assert len(hits) == 4 and hits == sorted(hits, key=lambda h: -h.score)
    assert all("Ayuntamiento" in h.chunk.title for h in hits)
    assert "BOE-A-2026-23041" in {h.chunk.doc_id for h in r.search("Torrox subalterno", k=1)}
    assert hits[0].chunk.title.startswith("Resolución")


def test_search_is_accent_insensitive_and_handles_empty_query() -> None:
    r = build()
    assert r.search("RESOLUCION") == r.search("resolución")
    assert r.search("de la") == []
    assert r.search("zzzxqv") == []


def test_hashing_embedder_is_deterministic_unit_norm_and_topical() -> None:
    e: Embedder = HashingEmbedder(256)
    a, b = e.embed("plazas de subalterno ayuntamiento"), e.embed("plazas subalterno ayuntamiento")
    c = e.embed("convenio financiación universidad")
    assert a == e.embed("plazas de subalterno ayuntamiento")
    assert abs(sum(x * x for x in a) - 1) < 1e-9
    assert dot(a, b) > dot(a, c)
    assert e.embed("de la") == [0.0] * 256


def test_index_persists_metadata(tmp_path: Path) -> None:
    from datetime import date

    db = str(tmp_path / "i.db")
    ch = Chunk("x#0", "x", "Título", "Dep", date(2026, 1, 2), "http://u", "texto sobre agua")
    SqliteFtsRetriever(db).index([ch])
    assert SqliteFtsRetriever(db).search("agua")[0].chunk == ch
