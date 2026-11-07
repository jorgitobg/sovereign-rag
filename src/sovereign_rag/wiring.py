"""Composition root: builds the offline stack (BOE XML + FTS5 + extractive model)."""

from __future__ import annotations

from pathlib import Path

from sovereign_rag.adapters.boe_xml import parse_boe
from sovereign_rag.adapters.fts5 import SqliteFtsRetriever
from sovereign_rag.application.ingest import ingest_files
from sovereign_rag.domain.models import IngestIssue

_PKG_DATA = Path(__file__).parent / "data"


def default_corpus_dir() -> Path:
    """Wheel installs ship the corpus under ``data/boe``; a source checkout uses the fixtures."""
    packaged = _PKG_DATA / "boe"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "boe"


def default_golden_path() -> Path:
    return _PKG_DATA / "golden.jsonl"


def default_paraphrase_golden_path() -> Path:
    return _PKG_DATA / "golden_paraphrase.jsonl"


def build_retriever(corpus: Path) -> tuple[SqliteFtsRetriever, list[IngestIssue]]:
    """Index every ``*.xml`` in ``corpus`` in memory. Raises FileNotFoundError if it is missing."""
    if not corpus.is_dir():
        raise FileNotFoundError(f"corpus directory not found: {corpus}")
    chunks, issues = ingest_files(corpus.glob("*.xml"), parse_boe)
    retriever = SqliteFtsRetriever()
    retriever.index(chunks)
    return retriever, issues
