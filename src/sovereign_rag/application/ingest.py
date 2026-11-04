"""US1: turn documents into chunks that carry citation metadata."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from sovereign_rag.domain.models import Chunk, Document, IngestIssue

DocumentParser = Callable[[bytes], Document]


def chunk_document(doc: Document, max_chars: int = 600) -> list[Chunk]:
    """Greedy paragraph packing: a chunk never splits a paragraph unless it alone exceeds
    max_chars. The title is a prefix of the first chunk's searchable text via metadata,
    not duplicated in every chunk."""
    pieces: list[str] = []
    buf = ""
    for para in doc.paragraphs:
        para = para.strip()
        if not para:
            continue
        if buf and len(buf) + 1 + len(para) > max_chars:
            pieces.append(buf)
            buf = ""
        while len(para) > max_chars:
            cut = para.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            pieces.append(para[:cut].strip())
            para = para[cut:].strip()
        buf = f"{buf} {para}".strip() if buf else para
    if buf:
        pieces.append(buf)
    return [
        Chunk(
            id=f"{doc.id}#{i}",
            doc_id=doc.id,
            title=doc.title,
            department=doc.department,
            published=doc.published,
            url=doc.url,
            text=text,
        )
        for i, text in enumerate(pieces)
    ]


def ingest_files(
    paths: Iterable[Path], parser: DocumentParser
) -> tuple[list[Chunk], list[IngestIssue]]:
    """Parse and chunk files. Unparsable ones are reported and skipped, never raised."""
    chunks: list[Chunk] = []
    issues: list[IngestIssue] = []
    for path in sorted(paths):
        try:
            doc = parser(path.read_bytes())
        except (ValueError, OSError) as exc:
            issues.append(IngestIssue(path.name, str(exc)))
            continue
        chunks.extend(chunk_document(doc))
    return chunks, issues
