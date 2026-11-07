from __future__ import annotations

from sovereign_rag.adapters.fts5 import SqliteFtsRetriever
from sovereign_rag.application.answer import stems
from sovereign_rag.application.synonyms import GROUPS, alternatives, canonical
from sovereign_rag.eval import evaluate, load_golden
from sovereign_rag.wiring import (
    build_retriever,
    default_corpus_dir,
    default_golden_path,
    default_paraphrase_golden_path,
)


def test_table_has_no_word_in_two_groups() -> None:
    words = [w for g in GROUPS for w in g]
    assert len(words) == len(set(words))


def test_canonical_and_alternatives() -> None:
    assert canonical("puesto") == canonical("vacante") == canonical("plaza") == "plaza"
    assert canonical("camion") == "camion" and alternatives("camion") == ()
    assert set(alternatives("puesto")) == {"plaza", "vacante"}


def test_stems_map_synonyms_to_one_stem_but_leave_other_words_alone() -> None:
    assert stems("puestos") == stems("plazas") == stems("vacante")
    assert stems("bomberos") != stems("plazas")


def test_retriever_finds_a_chunk_by_a_synonym_of_its_word() -> None:
    retriever, _ = build_retriever(default_corpus_dir())
    assert isinstance(retriever, SqliteFtsRetriever)
    docs = [h.chunk.doc_id for h in retriever.search("vacantes Subalterno Torrox", 3)]
    assert "BOE-A-2026-23041" in docs


def test_paraphrase_set_is_well_formed() -> None:
    cases = load_golden(default_paraphrase_golden_path())
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids))
    main_questions = {c.question for c in load_golden(default_golden_path())}
    assert not main_questions & {c.question for c in cases}
    corpus = {p.stem for p in default_corpus_dir().glob("*.xml")}
    assert all(set(c.gold_docs) <= corpus for c in cases)


def test_paraphrase_regression_floors() -> None:
    # Measured before synonyms: 4/12 answered. After: 12/12. Floors sit just under the
    # measured values to catch regressions; they are not targets.
    r = evaluate(load_golden(default_paraphrase_golden_path()), default_corpus_dir())
    assert r.answered >= 11
    assert r.citation_doc_correct == r.answered
    assert r.abstained_unanswerable >= 5
