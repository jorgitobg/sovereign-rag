# ADR 0001: Hexagonal layout with ports

Status: accepted (2026-11-04)

Domain (documents, chunks, citations, answer policy) has no I/O. Application services orchestrate ingest, retrieve and answer through ports: `DocumentSource`, `Retriever`, `Embedder`, `Generator`. Adapters: BOE XML parser, SQLite FTS5, hashing embedder, OpenAI-compatible HTTP generator, scripted fake generator. Tests exercise the domain and application with fakes and recorded fixtures; no test touches the network or a real model.

Trade-off: more files than a single script, in exchange for swappable backends and a deterministic test suite.
