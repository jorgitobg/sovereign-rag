import subprocess
import sys

import pytest

from sovereign_rag.demo import SAMPLE_QUESTIONS, main


def test_demo_answers_with_sources_and_abstains(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-23041" in out
    assert "Sin evidencia" in out
    assert out.count("Q: ") == len(SAMPLE_QUESTIONS)


def test_demo_accepts_a_custom_question(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["¿Cuál es la capital de Francia?"]) == 0
    out = capsys.readouterr().out
    assert out.count("Q: ") == 1 and "Sin evidencia" in out


def test_demo_fails_cleanly_on_missing_corpus(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--corpus", "/nonexistent-dir-xyz", "hola"]) == 2
    assert "corpus" in capsys.readouterr().err.lower()


def test_module_entry_points_run_as_scripts() -> None:
    for mod in ("sovereign_rag.demo", "sovereign_rag.eval"):
        done = subprocess.run(
            [sys.executable, "-m", mod], capture_output=True, text=True, check=False, timeout=60
        )
        assert done.returncode == 0, done.stderr
        assert done.stdout.strip()
