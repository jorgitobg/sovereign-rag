"""Golden evaluation: ``python -m sovereign_rag.eval`` or ``sovereign-rag-eval``.

Metrics are computed, never asserted: nothing here is tuned at print time.
"""

from __future__ import annotations

import argparse
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


def evaluate(cases: Sequence[GoldenCase], corpus: Path) -> EvalResult:
    retriever, _ = build_retriever(corpus)
    model = ExtractiveModel()
    indexed = {c.id: c for c in ingest_files(corpus.glob("*.xml"), parse_boe)[0]}
    hit_at: dict[int, int] = dict.fromkeys(KS, 0)
    answered = contains = doc_correct = c_total = c_valid = abstained_neg = 0
    n_pos = n_neg = 0
    failures: list[str] = []
    for case in cases:
        ans = answer_question(case.question, retriever, model)
        for c in ans.citations:
            c_total += 1
            ref = indexed.get(c.chunk_id)
            if ref and c.quote.rstrip("…") in ref.text and c.url == ref.url:
                c_valid += 1
        if not case.gold_docs:
            n_neg += 1
            if ans.abstained:
                abstained_neg += 1
            else:
                failures.append(case.id)
            continue
        n_pos += 1
        docs = [h.chunk.doc_id for h in retriever.search(case.question, max(KS))]
        for k in KS:
            if set(docs[:k]) & set(case.gold_docs):
                hit_at[k] += 1
        ok = False
        if not ans.abstained:
            answered += 1
            has = case.expect.casefold() in ans.text.casefold()
            right_doc = all(c.doc_id in case.gold_docs for c in ans.citations)
            contains += has
            doc_correct += right_doc
            ok = has and right_doc
        if not ok:
            failures.append(case.id)
    return EvalResult(
        n_pos, n_neg, hit_at, answered, contains, doc_correct, c_total, c_valid,
        abstained_neg, tuple(failures),
    )  # fmt: skip


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
    args = ap.parse_args(argv)
    try:
        cases = load_golden(args.golden or default_golden_path())
        result = evaluate(cases, args.corpus or default_corpus_dir())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
