"""Per-question diagnostics: versioned JSON output next to the unchanged text report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sovereign_rag.eval import (
    SCHEMA_VERSION,
    GoldenCase,
    evaluate,
    evaluate_detailed,
    load_golden,
    main,
    render,
    render_json,
)
from sovereign_rag.wiring import default_corpus_dir, default_golden_path


def detailed(path: Path | None = None) -> tuple[dict[str, Any], str]:
    golden = path or default_golden_path()
    result, cases = evaluate_detailed(load_golden(golden), default_corpus_dir())
    text = render_json(result, cases, golden, default_corpus_dir())
    return json.loads(text), text


def test_json_has_version_and_dataset_identity() -> None:
    doc, _ = detailed()
    golden = default_golden_path()
    assert doc["schema_version"] == SCHEMA_VERSION == 1
    assert doc["dataset"] == {
        "golden_file": "golden.jsonl",
        "golden_sha256": hashlib.sha256(golden.read_bytes()).hexdigest(),
        "cases": 40,
        "corpus_documents": len(list(default_corpus_dir().glob("*.xml"))),
    }


def test_output_is_deterministic_and_has_no_absolute_paths() -> None:
    first = detailed()[1]
    second = detailed()[1]
    assert first == second
    assert str(Path.home()) not in first and "/tmp" not in first


def test_summary_matches_the_text_report_numbers() -> None:
    doc, _ = detailed()
    cases = load_golden(default_golden_path())
    result = evaluate(cases, default_corpus_dir())
    summary = doc["summary"]
    assert summary["n_answerable"] == result.n_answerable
    assert summary["n_unanswerable"] == result.n_unanswerable
    assert summary["hit_at"] == {str(k): v for k, v in result.hit_at.items()}
    assert summary["answered"] == result.answered
    assert summary["answer_contains"] == result.answer_contains
    assert summary["citation_doc_correct"] == result.citation_doc_correct
    assert summary["citations_total"] == result.citations_total
    assert summary["citations_valid"] == result.citations_valid
    assert summary["abstained_unanswerable"] == result.abstained_unanswerable
    assert summary["failures"] == list(result.failures)


def test_per_case_rows_reproduce_every_aggregate() -> None:
    doc, _ = detailed()
    rows: list[dict[str, Any]] = doc["cases"]
    assert len(rows) == 40
    answerable = [r for r in rows if r["answerable"]]
    summary = doc["summary"]
    assert len(answerable) == summary["n_answerable"]
    assert len(rows) - len(answerable) == summary["n_unanswerable"]
    for k in ("1", "3", "5"):
        assert sum(r["hit_at"][k] for r in answerable) == summary["hit_at"][k]
    assert (
        sum(r["citations"]["all_gold_doc"] is True for r in answerable)
        == summary["citation_doc_correct"]
    )
    assert (
        sum(r["abstained"] for r in rows if not r["answerable"])
        == summary["abstained_unanswerable"]
    )
    assert sum(1 for r in answerable if not r["abstained"]) == summary["answered"]
    assert sum(r["answer_contains"] is True for r in answerable) == summary["answer_contains"]
    assert sum(r["citations"]["total"] for r in rows) == summary["citations_total"]
    assert sum(r["citations"]["valid"] for r in rows) == summary["citations_valid"]
    assert [r["id"] for r in rows if not r["passed"]] == summary["failures"]


def test_failed_rows_explain_why() -> None:
    doc, _ = detailed()
    rows: list[dict[str, Any]] = doc["cases"]
    failed = [r for r in rows if not r["passed"]]
    assert failed and all(r["failure_reasons"] for r in failed)
    assert all(r["failure_reasons"] == [] for r in rows if r["passed"])
    known = {
        "retrieval_miss",
        "abstained_on_answerable",
        "answer_missing_expected_text",
        "citation_wrong_doc",
        "answered_out_of_corpus",
    }
    assert {x for r in failed for x in r["failure_reasons"]} <= known


def test_abstentions_carry_the_pipelines_reason() -> None:
    cases = [
        GoldenCase("n1", "¿Cuál es la capital de Francia?", (), ""),
        GoldenCase(
            "t1",
            "¿Cuántas plazas de Subalterno convoca el Ayuntamiento de Torrox?",
            ("BOE-A-2026-23041",),
            "8 plazas",
        ),
        GoldenCase(
            "bad", "¿Cuántas plazas de Subalterno convoca Torrox?", ("BOE-A-2026-23097",), "zzz"
        ),
    ]
    result, rows = evaluate_detailed(cases, default_corpus_dir())
    by_id = {r.id: r for r in rows}
    assert by_id["n1"].abstained and by_id["n1"].abstain_reason == "no_evidence"
    assert by_id["n1"].passed and by_id["n1"].answer_contains is None
    assert by_id["t1"].passed and by_id["t1"].answer_text and by_id["t1"].abstain_reason == ""
    assert not by_id["bad"].passed
    assert set(by_id["bad"].failure_reasons) >= {"retrieval_miss", "answer_missing_expected_text"}
    assert result.failures == ("bad",)


def test_default_text_output_is_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert out.rstrip("\n") == render(
        evaluate(load_golden(default_golden_path()), default_corpus_dir())
    )
    assert out.startswith("cases: 26 answerable, 14 out-of-corpus\n")
    assert "answer contains expected text: 16/26 = 61.5%" in out


def test_json_flag_prints_only_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["schema_version"] == 1
    assert "hit@1" not in out


def test_json_flag_on_the_paraphrase_set_names_it(capsys: pytest.CaptureFixture[str]) -> None:
    from sovereign_rag.wiring import default_paraphrase_golden_path

    assert main(["--json", "--golden", str(default_paraphrase_golden_path())]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["dataset"]["golden_file"] == "golden_paraphrase.jsonl"
    assert doc["dataset"]["cases"] == 18
