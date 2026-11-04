"""Domain types: documents, chunks and retrieval hits. No I/O here."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    title: str
    department: str
    published: date | None
    url: str
    paragraphs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable passage that keeps enough metadata to be cited."""

    id: str
    doc_id: str
    title: str
    department: str
    published: date | None
    url: str
    text: str


@dataclass(frozen=True, slots=True)
class Hit:
    chunk: Chunk
    score: float


@dataclass(frozen=True, slots=True)
class IngestIssue:
    ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class Citation:
    """Pointer from one claim of an answer to the passage that supports it."""

    chunk_id: str
    doc_id: str
    title: str
    url: str
    claim: str
    quote: str


@dataclass(frozen=True, slots=True)
class Answer:
    """Either a cited answer, or an abstention with a machine-readable reason."""

    text: str
    citations: tuple[Citation, ...]
    abstained: bool
    reason: str = ""
