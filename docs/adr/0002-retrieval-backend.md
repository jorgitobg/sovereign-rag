# ADR 0002: Retrieval backend

Status: accepted (2026-11-04)

## Decision
Start with SQLite FTS5 (BM25) from the standard library. A deterministic hashing-trick embedder is included for a later fusion step (reciprocal-rank fusion) but is not used for retrieval in v0.1. No services, no model download, zero runtime dependencies, so the demo runs anywhere.

## Alternatives
- pgvector: better at scale, needs a server; planned as a second `Retriever` adapter.
- Neural embedders: better semantics, add a download and non-determinism; can plug in behind `Embedder`.

## Consequences
Lexical-leaning quality on small corpora; the golden evaluation reports measured hit-rate rather than claims. Spanish stemming is out of scope for v0; FTS5 `unicode61` with accent removal is used.
