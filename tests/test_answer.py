from collections.abc import Sequence
from datetime import date

from sovereign_rag.application.answer import ABSTENTION_TEXT, answer_question
from sovereign_rag.domain.models import Answer, Chunk, Hit
from sovereign_rag.domain.ports import ModelClient, Retriever


def chunk(i: int, title: str, text: str) -> Chunk:
    return Chunk(f"D{i}#0", f"D{i}", title, "Dep", date(2026, 1, 1), f"https://x/{i}", text)


class FakeRetriever:
    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self.chunks = list(chunks)

    def index(self, chunks: Sequence[Chunk]) -> None:
        self.chunks = list(chunks)

    def search(self, query: str, k: int = 5) -> list[Hit]:
        return [Hit(c, 1.0) for c in self.chunks[:k]]


class ScriptedModel:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, int]] = []

    def answer(self, question: str, passages: Sequence[Chunk]) -> str:
        self.calls.append((question, len(passages)))
        return self.reply


TORROX = chunk(1, "Ayuntamiento de Torrox", "Ocho plazas de Subalterno por concurso-oposición.")
Q = "¿Cuántas plazas de Subalterno convoca Torrox?"


def run(reply: str, chunks: Sequence[Chunk] = (TORROX,)) -> tuple[ScriptedModel, Answer]:
    model = ScriptedModel(reply)
    r: Retriever = FakeRetriever(chunks)
    m: ModelClient = model
    return model, answer_question(Q, r, m)


def test_supported_answer_carries_resolvable_citation() -> None:
    model, ans = run("Ocho plazas de Subalterno por concurso-oposición. [1]")
    assert not ans.abstained and ans.reason == "" and model.calls == [(Q, 1)]
    assert [c.chunk_id for c in ans.citations] == ["D1#0"]
    c = ans.citations[0]
    assert c.url == "https://x/1" and c.doc_id == "D1" and c.title == "Ayuntamiento de Torrox"
    assert c.claim == "Ocho plazas de Subalterno por concurso-oposición."
    assert c.quote == "Ocho plazas de Subalterno por concurso-oposición."
    assert "[1]" in ans.text


def test_no_hits_abstains_without_calling_model() -> None:
    model, ans = run("irrelevante [1]", chunks=())
    assert ans.abstained and ans.reason == "no_evidence"
    assert ans.text == ABSTENTION_TEXT and ans.citations == () and model.calls == []


def test_weak_lexical_overlap_abstains() -> None:
    other = chunk(2, "Ayuntamiento de Sevilla", "Convocatoria de plazas de bombero.")
    model = ScriptedModel("x [1]")
    ans = answer_question("¿Cuánto cuesta una hipoteca en Sevilla?", FakeRetriever([other]), model)
    assert ans.abstained and ans.reason == "no_evidence" and model.calls == []


def test_question_with_a_term_absent_from_the_passage_abstains() -> None:
    """3 of 5 content terms match, but the discriminating ones (city, job) do not."""
    p = chunk(2, "Ayuntamiento de Girona", "Cinco plazas de Personal administrativo, turno libre.")
    model = ScriptedModel("Cinco plazas de Personal administrativo. [1]")
    q = "¿Cuántas plazas de bombero convoca el Ayuntamiento de Sevilla?"
    ans = answer_question(q, FakeRetriever([p]), model)
    assert ans.abstained and ans.reason == "no_evidence" and model.calls == []


def test_proper_noun_in_question_missing_from_passage_abstains() -> None:
    p = chunk(2, "Ayuntamiento de Torrox", "Ocho plazas de Subalterno por concurso-oposición.")
    model = ScriptedModel("Ocho plazas de Subalterno. [1]")
    ans = answer_question(
        "¿Qué plazas de Subalterno convoca el Ayuntamiento de Valencia?", FakeRetriever([p]), model
    )
    assert ans.abstained and ans.reason == "no_evidence" and model.calls == []


def test_uncited_model_output_is_never_returned() -> None:
    _, ans = run("Ocho plazas de Subalterno.")
    assert ans.abstained and ans.reason == "uncited_output"
    assert ans.citations == () and ans.text == ABSTENTION_TEXT


def test_citation_to_unknown_passage_is_rejected() -> None:
    _, ans = run("Ocho plazas de Subalterno. [2]")
    assert ans.abstained and ans.reason == "invalid_citation"


def test_mixed_valid_and_invalid_marker_is_rejected() -> None:
    _, ans = run("Ocho plazas. [1] Otra cosa. [7]")
    assert ans.abstained and ans.reason == "invalid_citation"


def test_empty_model_output_abstains() -> None:
    _, ans = run("   ")
    assert ans.abstained and ans.reason == "empty_output"


def test_question_without_content_terms_abstains() -> None:
    model = ScriptedModel("x [1]")
    ans = answer_question("¿Y de la?", FakeRetriever([TORROX]), model)
    assert ans.abstained and ans.reason == "no_evidence" and model.calls == []


def test_repeated_marker_yields_one_citation_per_segment() -> None:
    two = [TORROX, chunk(2, "Ayuntamiento de Torrox", "Plazas de Subalterno, turno libre.")]
    _, ans = run("Ocho plazas. [1] Turno libre. [2] Ocho plazas otra vez. [1]", two)
    assert not ans.abstained
    assert [c.chunk_id for c in ans.citations] == ["D1#0", "D2#0", "D1#0"]


def test_long_passage_quote_is_truncated() -> None:
    long = chunk(1, "Ayuntamiento de Torrox", "Plazas de Subalterno. " + "relleno " * 100)
    _, ans = run("Plazas de Subalterno. [1]", [long])
    assert len(ans.citations[0].quote) <= 241 and ans.citations[0].quote.endswith("…")
