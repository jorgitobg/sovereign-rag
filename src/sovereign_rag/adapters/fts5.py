"""SQLite FTS5 (BM25) retriever. Standard library only, in-memory or on disk."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections.abc import Sequence
from datetime import date

from sovereign_rag.domain.models import Chunk, Hit

_STOP = frozenset(
    {
        "a",
        "al",
        "con",
        "de",
        "del",
        "el",
        "en",
        "la",
        "las",
        "lo",
        "los",
        "para",
        "por",
        "que",
        "se",
        "su",
        "sus",
        "un",
        "una",
        "y",
        "o",
        "u",
        "es",
    }
)


def fold(text: str) -> str:
    """Lowercase and strip accents so 'Resolución' matches 'resolucion'."""
    nfd = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def query_terms(query: str) -> list[str]:
    toks = re.findall(r"\w+", fold(query))
    return [t for t in toks if t not in _STOP and len(t) > 1]


class SqliteFtsRetriever:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5("
            "text, title, id UNINDEXED, doc_id UNINDEXED, department UNINDEXED, "
            "published UNINDEXED, url UNINDEXED, raw UNINDEXED, raw_title UNINDEXED, "
            "tokenize='unicode61 remove_diacritics 2')"
        )

    def index(self, chunks: Sequence[Chunk]) -> None:
        self._db.executemany(
            "INSERT INTO chunks(text, title, id, doc_id, department, published, url, "
            "raw, raw_title) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    fold(c.text),
                    fold(c.title),
                    c.id,
                    c.doc_id,
                    c.department,
                    c.published.isoformat() if c.published else "",
                    c.url,
                    c.text,
                    c.title,
                )
                for c in chunks
            ],
        )
        self._db.commit()

    def search(self, query: str, k: int = 5) -> list[Hit]:
        terms = query_terms(query)
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        rows = self._db.execute(
            "SELECT id, doc_id, raw_title, department, published, url, raw, bm25(chunks, 1.0, 2.0) "
            "FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks, 1.0, 2.0) LIMIT ?",
            (match, k),
        ).fetchall()
        hits: list[Hit] = []
        for cid, doc_id, title, dept, pub, url, raw, rank in rows:
            chunk = Chunk(
                id=cid,
                doc_id=doc_id,
                title=title,
                department=dept,
                published=date.fromisoformat(pub) if pub else None,
                url=url,
                text=raw,
            )
            hits.append(Hit(chunk, -float(rank)))  # bm25() is negative: higher is better
        return hits
