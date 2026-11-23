"""Golden evaluation: ``python -m sovereign_rag.eval`` or ``sovereign-rag-eval``.

Metrics are computed, never asserted: nothing here is tuned at print time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sovereign_rag.adapters.boe_xml import parse_boe
from sovereign_rag.adapters.extractive import ExtractiveModel
from sovereign_rag.application.answer import answer_question
from sovereign_rag.application.ingest import ingest_files
from sovereign_rag.wiring import build_retriever, default_corpus_dir, default_golden_path

KS = (1, 3, 5)
SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class GoldenCase:
    id: str
    question: str
    gold_docs: tuple[str, ...]  # empty = out-of-corpus: the system must abstain
    expect: str  # substring the answer must contain (answerable cases only)


@dataclass(frozen=True, slots=True)
class EvalResult:
    n_answerable: int
    n_unanswerable: int
    hit_at: dict[int, int]  # k -> answerable cases with a gold document among the top-k chunks
    answered: int  # answerable cases that got a cited answer (not an abstention)
    answer_contains: int  # ...of which the answer contains the expected substring
    citation_doc_correct: int  # ...of which every citation points to a gold document
    citations_total: int  # citations emitted across all non-abstained answers
    citations_valid: int  # ...that resolve to an indexed chunk with verbatim quote and URL
    abstained_unanswerable: int
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CitationStats:
    total: int  # citations emitted for this case
    valid: int  # ...that resolve to an indexed chunk with verbatim quote and URL


@dataclass(frozen=True, slots=True)
class CaseResult:
    """What happened to one golden question: the row behind every aggregate number."""

    id: str
    question: str
    answerable: bool
    gold_docs: tuple[str, ...]
    retrieved_docs: tuple[str, ...]  # document id of each of the top-5 chunks, in rank order
    hit_at: dict[int, bool] | None  # None for out-of-corpus questions
    abstained: bool
    abstain_reason: str  # the pipeline's machine-readable reason; empty when it answered
    answer_text: str | None
    answer_contains: bool | None  # None when not applicable (abstained or out-of-corpus)
    all_gold_doc: bool | None
    citations: CitationStats
    passed: bool
    failure_reasons: tuple[str, ...]


def load_golden(path: Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            cases.append(
                GoldenCase(
                    str(raw["id"]),
                    str(raw["question"]),
                    tuple(raw["gold_docs"]),
                    str(raw["expect"]),
                )
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path.name}: line {n}: {exc!r}") from exc
    return cases


def evaluate_detailed(
    cases: Sequence[GoldenCase], corpus: Path
) -> tuple[EvalResult, tuple[CaseResult, ...]]:
    """Run every case once; return the aggregate and the per-case rows it was built from."""
    retriever, _ = build_retriever(corpus)
    model = ExtractiveModel()
    indexed = {c.id: c for c in ingest_files(corpus.glob("*.xml"), parse_boe)[0]}
    hit_at: dict[int, int] = dict.fromkeys(KS, 0)
    answered = contains = doc_correct = c_total = c_valid = abstained_neg = 0
    n_pos = n_neg = 0
    failures: list[str] = []
    rows: list[CaseResult] = []
    for case in cases:
        ans = answer_question(case.question, retriever, model)
        valid = 0
        for c in ans.citations:
            c_total += 1
            ref = indexed.get(c.chunk_id)
            if ref and c.quote.rstrip("…") in ref.text and c.url == ref.url:
                c_valid += 1
                valid += 1
        citations = CitationStats(len(ans.citations), valid)
        if not case.gold_docs:
            n_neg += 1
            if ans.abstained:
                abstained_neg += 1
            else:
                failures.append(case.id)
            rows.append(
                CaseResult(
                    case.id, case.question, False, case.gold_docs, (), None, ans.abstained,
                    ans.reason, None if ans.abstained else ans.text, None, None, citations,
                    ans.abstained, () if ans.abstained else ("answered_out_of_corpus",),
                )
            )  # fmt: skip
            continue
        n_pos += 1
        docs = [h.chunk.doc_id for h in retriever.search(case.question, max(KS))]
        hits = {k: bool(set(docs[:k]) & set(case.gold_docs)) for k in KS}
        for k in KS:
            hit_at[k] += hits[k]
        ok = False
        has: bool | None = None
        right_doc: bool | None = None
        if not ans.abstained:
            answered += 1
            has = case.expect.casefold() in ans.text.casefold()
            right_doc = all(c.doc_id in case.gold_docs for c in ans.citations)
            contains += has
            doc_correct += right_doc
            ok = has and right_doc
        if not ok:
            failures.append(case.id)
        reasons: list[str] = []
        if not ok:
            if not hits[max(KS)]:
                reasons.append("retrieval_miss")
            if ans.abstained:
                reasons.append("abstained_on_answerable")
            else:
                if not has:
                    reasons.append("answer_missing_expected_text")
                if not right_doc:
                    reasons.append("citation_wrong_doc")
        rows.append(
            CaseResult(
                case.id, case.question, True, case.gold_docs, tuple(docs), hits, ans.abstained,
                ans.reason, None if ans.abstained else ans.text, has, right_doc, citations,
                ok, tuple(reasons),
            )
        )  # fmt: skip
    result = EvalResult(
        n_pos, n_neg, hit_at, answered, contains, doc_correct, c_total, c_valid,
        abstained_neg, tuple(failures),
    )  # fmt: skip
    return result, tuple(rows)


def evaluate(cases: Sequence[GoldenCase], corpus: Path) -> EvalResult:
    return evaluate_detailed(cases, corpus)[0]


def render_json(result: EvalResult, rows: Sequence[CaseResult], golden: Path, corpus: Path) -> str:
    """Versioned machine-readable report. Paths are reduced to file names (no local paths)."""
    document = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "golden_file": golden.name,
            "golden_sha256": hashlib.sha256(golden.read_bytes()).hexdigest(),
            "cases": len(rows),
            "corpus_documents": len(list(corpus.glob("*.xml"))),
        },
        "summary": {
            "n_answerable": result.n_answerable,
            "n_unanswerable": result.n_unanswerable,
            "hit_at": {str(k): v for k, v in result.hit_at.items()},
            "answered": result.answered,
            "answer_contains": result.answer_contains,
            "citation_doc_correct": result.citation_doc_correct,
            "citations_total": result.citations_total,
            "citations_valid": result.citations_valid,
            "abstained_unanswerable": result.abstained_unanswerable,
            "failures": list(result.failures),
        },
        "cases": [
            {
                "id": r.id,
                "question": r.question,
                "answerable": r.answerable,
                "gold_docs": list(r.gold_docs),
                "retrieved_docs": list(r.retrieved_docs),
                "hit_at": None if r.hit_at is None else {str(k): v for k, v in r.hit_at.items()},
                "abstained": r.abstained,
                "abstain_reason": r.abstain_reason,
                "answer_text": r.answer_text,
                "answer_contains": r.answer_contains,
                "citations": {
                    "total": r.citations.total,
                    "valid": r.citations.valid,
                    "all_gold_doc": r.all_gold_doc,
                },
                "passed": r.passed,
                "failure_reasons": list(r.failure_reasons),
            }
            for r in rows
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} = {100 * a / b:.1f}%" if b else f"{a}/{b} = n/a"


def render(r: EvalResult) -> str:
    lines = [
        f"cases: {r.n_answerable} answerable, {r.n_unanswerable} out-of-corpus",
        *(f"hit@{k}: {_pct(r.hit_at[k], r.n_answerable)}" for k in KS),
        f"answered (answerable): {_pct(r.answered, r.n_answerable)}",
        f"answer contains expected text: {_pct(r.answer_contains, r.n_answerable)}",
        f"all citations point to gold doc: {_pct(r.citation_doc_correct, r.n_answerable)}",
        f"citation validity: {_pct(r.citations_valid, r.citations_total)}",
        f"abstention (out-of-corpus): {_pct(r.abstained_unanswerable, r.n_unanswerable)}",
        f"failed cases: {', '.join(r.failures) if r.failures else 'none'}",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sovereign-rag-eval", description=__doc__)
    ap.add_argument("--corpus", type=Path, default=None)
    ap.add_argument("--golden", type=Path, default=None)
    ap.add_argument(
        "--json", action="store_true", help="print per-question diagnostics as versioned JSON"
    )
    args = ap.parse_args(argv)
    golden = args.golden or default_golden_path()
    corpus = args.corpus or default_corpus_dir()
    try:
        result, rows = evaluate_detailed(load_golden(golden), corpus)
        output = render_json(result, rows, golden, corpus) if args.json else render(result)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
