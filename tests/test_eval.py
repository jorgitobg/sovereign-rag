import json
from pathlib import Path

import pytest

from sovereign_rag.eval import GoldenCase, evaluate, load_golden, main, render
from sovereign_rag.wiring import default_corpus_dir, default_golden_path


def test_golden_dataset_is_well_formed() -> None:
    cases = load_golden(default_golden_path())
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))
    answerable = [c for c in cases if c.gold_docs]
    assert len(answerable) >= 20 and len(cases) - len(answerable) >= 10
    assert all(c.expect for c in answerable)
    corpus = {p.stem for p in default_corpus_dir().glob("*.xml")}
    assert all(set(c.gold_docs) <= corpus for c in cases)


def test_load_golden_rejects_bad_lines(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(json.dumps({"id": "a"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        load_golden(p)


def test_evaluate_is_deterministic_and_internally_consistent() -> None:
    cases = load_golden(default_golden_path())
    r1 = evaluate(cases, default_corpus_dir())
    assert r1 == evaluate(cases, default_corpus_dir())
    assert r1.n_answerable + r1.n_unanswerable == len(cases)
    assert r1.hit_at[1] <= r1.hit_at[3] <= r1.hit_at[5] <= r1.n_answerable
    assert 0 <= r1.citations_valid <= r1.citations_total
    assert r1.abstained_unanswerable <= r1.n_unanswerable


def test_regression_floors_on_the_committed_dataset() -> None:
    # Floors sit just under the values measured on the committed dataset (README has the exact
    # numbers); they catch regressions, they are not targets.
    r = evaluate(load_golden(default_golden_path()), default_corpus_dir())
    assert r.hit_at[5] / r.n_answerable >= FLOOR_HIT5
    assert r.citations_valid == r.citations_total > 0
    assert r.abstained_unanswerable / r.n_unanswerable >= FLOOR_ABSTAIN


FLOOR_HIT5 = 0.95
FLOOR_ABSTAIN = 0.9


def test_evaluate_scores_a_tiny_dataset() -> None:
    cases = [
        GoldenCase(
            "t1",
            "¿Cuántas plazas de Subalterno convoca el Ayuntamiento de Torrox?",
            ("BOE-A-2026-23041",),
            "8 plazas",
        ),
        GoldenCase("t2", "¿Cuál es la capital de Francia?", (), ""),
    ]
    r = evaluate(cases, default_corpus_dir())
    assert (r.n_answerable, r.n_unanswerable) == (1, 1)
    assert r.hit_at[1] == 1 and r.answer_contains == 1 and r.abstained_unanswerable == 1
    assert r.failures == ()


def test_wrong_expectation_is_reported_as_failure() -> None:
    cases = [
        GoldenCase(
            "bad", "¿Cuántas plazas de Subalterno convoca Torrox?", ("BOE-A-2026-23097",), "zzz"
        )
    ]
    r = evaluate(cases, default_corpus_dir())
    assert r.hit_at[5] == 0 and r.answer_contains == 0 and r.failures == ("bad",)


def test_render_and_main_print_all_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    for key in ("hit@1", "hit@3", "hit@5", "citation validity", "abstention (out-of-corpus)"):
        assert key in out
    assert "hit@5" in render(evaluate(load_golden(default_golden_path()), default_corpus_dir()))


def test_main_fails_cleanly_on_missing_inputs(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--corpus", "/nonexistent-dir-xyz"]) == 2
    assert main(["--golden", "/nonexistent.jsonl"]) == 2
    assert capsys.readouterr().err.count("error:") == 2
