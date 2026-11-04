# Spec 0001: sovereign-rag

Corpus: BOE disposition XML from the open-data service (verified live 2026-11-04: the daily summary API returns JSON with 87 `BOE-A` items for 2026-11-03; each item resolves to XML at `diario_boe/xml.php?id=`). See `tests/fixtures/boe/SOURCES.md`. Fixtures are institutional/normative documents only; documents that list candidates or other private individuals are excluded (only signing public office-holders are named).

## Stories

### US1: Ingest
As a user I want BOE XML documents turned into chunks with metadata so that answers can be traced.
- Given a BOE XML document, when ingested, then chunks keep id, title, department, publication date and source URL.
- Given an unparsable file, when ingested, then it is reported and skipped.

### US2: Retrieve
- Given an index of the fixtures, when I query "convocatoria plaza ayuntamiento", then the top results come from matching documents, ranked, with scores, through a `Retriever` port.
- v0.1 retrieves with SQLite FTS5 (BM25) only. The hashing embedder exists and is tested but is not wired into retrieval; fusing it by reciprocal-rank fusion is a later story.

### US3: Cited answers
- Given retrieved passages that cover the question, when an answer is produced, then it is a list of claims each followed by `[n]` markers; every marker resolves to a passage (chunk id, document id, title, source URL, verbatim quote) and the claim shares at least half of its content terms with that passage.
- Given no passage that covers the question (at least 75% of its content terms, and every capitalised name in it), when asked, then the answer is "Sin evidencia en el corpus" with zero citations and the model is not called.
- Given model output that is empty, has no markers, cites an unknown passage or has an unsupported claim, when validated, then it is replaced by an abstention carrying a reason (`empty_output`, `uncited_output`, `invalid_citation`, `unsupported_claim`). Uncited text is never shown.

### US4: Model port
- Given a `ModelClient` port (`answer(question, passages) -> str`), when the offline demo runs, then it uses a deterministic extractive adapter that quotes the best-matching sentence and cites it. It uses no LLM and no network and cannot paraphrase or combine facts.
- An OpenAI-compatible HTTP adapter is a later story (not in v0.1); the application validates citations regardless of the adapter.

### US5: Golden evaluation
- Given a golden Q&A file, when `python -m sovereign_rag.eval` runs, then it prints hit@1/3/5, answer-contains rate, citation validity and abstention rate on out-of-corpus questions, all computed from `src/sovereign_rag/data/golden.jsonl` (26 answerable and 14 out-of-corpus questions over the fixtures) and printed with their raw counts.

### US6: Offline demo
- Given no network and no keys, when `python -m sovereign_rag.demo` runs after `pip install -e .`, then it ingests the fixtures and answers sample questions with citations, abstaining on out-of-corpus ones.

## Non-goals
No hosted services, no scraping beyond the official API, no legal advice.
