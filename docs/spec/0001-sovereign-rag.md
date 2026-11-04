# Spec 0001: sovereign-rag

Corpus: BOE disposition XML from the open-data service (verified live 2026-11-04: the daily summary API returns JSON with 87 `BOE-A` items for 2026-11-03; each item resolves to XML at `diario_boe/xml.php?id=`). See `tests/fixtures/boe/SOURCES.md`.

## Stories

### US1: Ingest
As a user I want BOE XML documents turned into chunks with metadata so that answers can be traced.
- Given a BOE XML document, when ingested, then chunks keep id, title, department, publication date and source URL.
- Given an unparsable file, when ingested, then it is reported and skipped.

### US2: Retrieve
- Given an index of the fixtures, when I query "convocatoria plaza ayuntamiento", then the top results come from matching documents, ranked, with scores, through a `Retriever` port.
- Given two retriever implementations (SQLite FTS5 and hashing-embedding), when fused, then results combine by reciprocal-rank fusion.

### US3: Cited answers
- Given retrieved chunks, when an answer is produced, then every claim cites chunk ids with source URLs.
- Given no chunk above the relevance threshold, when asked, then the answer is "no evidence in the corpus" with zero citations.

### US4: Local model
- Given any OpenAI-compatible endpoint behind a `Generator` port, when configured, then answers are generated locally; tests use a scripted fake.

### US5: Golden evaluation
- Given a golden Q&A file, when `python -m sovereign_rag.eval` runs, then it prints hit-rate@k and refusal accuracy computed from the fixtures.

### US6: Offline demo
- Given no network and no keys, when `python -m sovereign_rag.demo` runs, then it ingests the fixtures and answers sample questions with citations.

## Non-goals
No hosted services, no scraping beyond the official API, no legal advice.
