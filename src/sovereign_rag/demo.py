"""Offline demo: ``python -m sovereign_rag.demo`` or ``sovereign-rag-demo``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from sovereign_rag.adapters.extractive import ExtractiveModel
from sovereign_rag.application.answer import answer_question
from sovereign_rag.wiring import build_retriever, default_corpus_dir

SAMPLE_QUESTIONS = (
    "¿Cuántas plazas de Subalterno convoca el Ayuntamiento de Torrox?",
    "¿Cuál es el plazo de presentación de solicitudes en la convocatoria de Borriana?",
    "¿Cuántos días tienen los interesados para personarse en el recurso 2067/2026?",
    "¿Cuál es la capital de Francia?",
    "¿Cuántas plazas de bombero convoca el Ayuntamiento de Sevilla?",
)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sovereign-rag-demo", description=__doc__)
    ap.add_argument("questions", nargs="*", help="questions (default: built-in samples)")
    ap.add_argument("--corpus", type=Path, default=None, help="directory with BOE XML files")
    args = ap.parse_args(argv)
    try:
        retriever, issues = build_retriever(args.corpus or default_corpus_dir())
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for issue in issues:
        print(f"warning: skipped {issue.ref}: {issue.reason}", file=sys.stderr)
    model = ExtractiveModel()
    for question in args.questions or SAMPLE_QUESTIONS:
        ans = answer_question(question, retriever, model)
        print(f"Q: {question}")
        if ans.abstained:
            print(f"A: {ans.text} (motivo: {ans.reason})")
        else:
            print(f"A: {ans.text}")
            seen: set[str] = set()
            for c in ans.citations:
                if c.chunk_id not in seen:
                    seen.add(c.chunk_id)
                    print(f"   fuente {c.chunk_id}: {c.title}")
                    print(f"   {c.url}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
