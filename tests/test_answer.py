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
    _, ans = run("Ocho plazas de Subalterno. [1]", [long])
    assert len(ans.citations[0].quote) <= 241 and ans.citations[0].quote.endswith("…")


# --- S05: requested-attribute evidence (RED first) ---

SALARY_Q = "¿Cuánto cobra un Subalterno en el Ayuntamiento de Torrox?"
COUNT_PASSAGE = chunk(
    3,
    "Ayuntamiento de Torrox",
    "Ocho plazas de Subalterno/a por concurso-oposición, turno libre.",
)
SALARY_PASSAGE = chunk(
    4,
    "Ayuntamiento de Torrox",
    "Ocho plazas de Subalterno/a. El sueldo base del puesto es de 1.200 euros mensuales.",
)


def test_salary_question_citing_the_count_sentence_abstains() -> None:
    """Regression for t05: salary asked, but the cited claim is about the number of posts."""
    ans = answer_question(
        SALARY_Q,
        FakeRetriever([COUNT_PASSAGE]),
        ScriptedModel("Ocho plazas de Subalterno/a por concurso-oposición, turno libre. [1]"),
    )
    assert ans.abstained and ans.reason == "missing_requested_attribute"


def test_salary_question_citing_the_salary_sentence_is_answered() -> None:
    ans = answer_question(
        SALARY_Q,
        FakeRetriever([SALARY_PASSAGE]),
        ScriptedModel("El sueldo base del puesto es de 1.200 euros mensuales. [1]"),
    )
    assert not ans.abstained and ans.reason == ""


def test_salary_question_needs_salary_evidence_in_the_cited_claim_not_just_the_title() -> None:
    """The passage covers the question, but its body has no salary fact; the title is not used."""
    body_without_salary = chunk(
        5, "Ayuntamiento de Torrox", "Ocho plazas de Subalterno/a por concurso-oposición."
    )
    ans = answer_question(
        SALARY_Q,
        FakeRetriever([body_without_salary]),
        ScriptedModel("Ocho plazas de Subalterno/a por concurso-oposición. [1]"),
    )
    assert ans.abstained and ans.reason == "missing_requested_attribute"


DEADLINE_Q = "¿Cuál es el plazo de presentación de solicitudes en la convocatoria de Borriana?"
MIXED_PASSAGE = chunk(
    6,
    "Ayuntamiento de Borriana",
    "Se convocan nueve plazas de Agente de la policía local, turno libre. "
    "El plazo de presentación de solicitudes será de diez días hábiles.",
)


def test_deadline_question_citing_the_count_sentence_abstains() -> None:
    """Deadline asked, but the cited claim talks about the number of posts."""
    ans = answer_question(
        DEADLINE_Q,
        FakeRetriever([MIXED_PASSAGE]),
        ScriptedModel("Se convocan nueve plazas de Agente de la policía local, turno libre. [1]"),
    )
    assert ans.abstained and ans.reason == "missing_requested_attribute"


def test_deadline_question_citing_the_deadline_sentence_is_answered() -> None:
    ans = answer_question(
        DEADLINE_Q,
        FakeRetriever([MIXED_PASSAGE]),
        ScriptedModel("El plazo de presentación de solicitudes será de diez días hábiles. [1]"),
    )
    assert not ans.abstained and ans.reason == ""


def test_count_question_with_both_facts_citing_the_salary_sentence_abstains() -> None:
    """Wrong-fact cited output with both facts present in the passage: quantity asked."""
    mixed = chunk(
        7,
        "Ayuntamiento de Torrox",
        "El sueldo base del puesto es de 1.200 euros mensuales. "
        "Se convocan ocho plazas de Subalterno/a, turno libre.",
    )
    q = "¿Cuántas plazas de Subalterno convoca el Ayuntamiento de Torrox?"
    ans = answer_question(
        q,
        FakeRetriever([mixed]),
        ScriptedModel("El sueldo base del puesto es de 1.200 euros mensuales. [1]"),
    )
    assert ans.abstained and ans.reason == "missing_requested_attribute"


def test_salary_question_with_mixed_passage_citing_salary_sentence_is_answered() -> None:
    mixed = chunk(
        8,
        "Ayuntamiento de Torrox",
        "Se convocan ocho plazas de Subalterno/a, turno libre. "
        "El sueldo base del puesto es de 1.200 euros mensuales.",
    )
    ans = answer_question(
        SALARY_Q,
        FakeRetriever([mixed]),
        ScriptedModel("El sueldo base del puesto es de 1.200 euros mensuales. [1]"),
    )
    assert not ans.abstained and "1.200 euros" in ans.citations[0].claim


# --- bounded fix round 2 (RED first) ---

from sovereign_rag.application.answer import _attribute  # noqa: E402  # pyright: ignore[reportPrivateUsage]


def test_sueldo_is_recognized_as_salary_intent() -> None:
    """Regression: the advertised word 'sueldo' did not match the 6-char normaliser."""
    assert _attribute("¿Cuál es el sueldo?") == "salary"


def test_sueldo_question_citing_the_count_sentence_abstains() -> None:
    q = "¿Cuál es el sueldo de un Subalterno en el Ayuntamiento de Torrox?"
    ans = answer_question(
        q,
        FakeRetriever([COUNT_PASSAGE]),
        ScriptedModel("Ocho plazas de Subalterno/a por concurso-oposición, turno libre. [1]"),
    )
    assert ans.abstained and ans.reason == "missing_requested_attribute"


def test_sueldo_question_citing_the_salary_sentence_is_answered() -> None:
    q = "¿Cuál es el sueldo de un Subalterno en el Ayuntamiento de Torrox?"
    ans = answer_question(
        q,
        FakeRetriever([SALARY_PASSAGE]),
        ScriptedModel("El sueldo base del puesto es de 1.200 euros mensuales. [1]"),
    )
    assert not ans.abstained and ans.reason == ""


ONE_PLAZA = chunk(
    9,
    "Ayuntamiento de Torrox",
    "El Ayuntamiento de Torrox convoca una plaza de Subalterno.",
)
ONE_Q = "¿Cuántas plazas de Subalterno convoca el Ayuntamiento de Torrox?"


def test_singular_una_plaza_count_is_answered() -> None:
    """Regression: 'una' is a retrieval stopword, so the cardinal check lost it."""
    ans = answer_question(
        ONE_Q, FakeRetriever([ONE_PLAZA]), ScriptedModel("Una plaza de Subalterno. [1]")
    )
    assert not ans.abstained and ans.reason == ""


def test_numeric_one_post_count_is_answered() -> None:
    ans = answer_question(
        ONE_Q, FakeRetriever([ONE_PLAZA]), ScriptedModel("1 plaza de Subalterno. [1]")
    )
    assert not ans.abstained and ans.reason == ""


def test_count_claim_stating_both_headcount_and_amount_is_answered() -> None:
    """Only digits *inside a monetary amount* are excluded, not every digit."""
    both = chunk(
        10,
        "Ayuntamiento de Torrox",
        "Se convocan 8 plazas de Subalterno y la retribución es de 1200 euros.",
    )
    ans = answer_question(
        ONE_Q,
        FakeRetriever([both]),
        ScriptedModel("Se convocan 8 plazas de Subalterno y la retribución es de 1200 euros. [1]"),
    )
    assert not ans.abstained and ans.reason == ""


def test_salary_body_absent_abstains_before_calling_the_model() -> None:
    model = ScriptedModel("Ocho plazas de Subalterno/a por concurso-oposición, turno libre. [1]")
    ans = answer_question(SALARY_Q, FakeRetriever([COUNT_PASSAGE]), model)
    assert ans.abstained and ans.reason == "missing_requested_attribute" and model.calls == []


def test_deadline_body_absent_abstains_before_calling_the_model() -> None:
    body = chunk(
        11,
        "Ayuntamiento de Borriana",
        "La presentación de solicitudes se realiza dentro de la convocatoria por vía electrónica.",
    )
    model = ScriptedModel("La presentación de solicitudes se realiza por vía electrónica. [1]")
    ans = answer_question(DEADLINE_Q, FakeRetriever([body]), model)
    assert ans.abstained and ans.reason == "missing_requested_attribute" and model.calls == []


def test_title_only_salary_evidence_abstains_before_calling_the_model() -> None:
    titled = chunk(
        12,
        "Sueldo y retribuciones del Subalterno — Ayuntamiento de Torrox",
        "Ocho plazas de Subalterno/a por concurso-oposición.",
    )
    model = ScriptedModel("Ocho plazas de Subalterno/a por concurso-oposición. [1]")
    ans = answer_question(SALARY_Q, FakeRetriever([titled]), model)
    assert ans.abstained and ans.reason == "missing_requested_attribute" and model.calls == []


def test_euro_prefix_amount_is_not_a_headcount() -> None:
    mixed = chunk(
        13,
        "Ayuntamiento de Torrox",
        "El sueldo base del puesto es de €1200 mensuales. "
        "Se convocan ocho plazas de Subalterno/a, turno libre.",
    )
    ans = answer_question(
        ONE_Q,
        FakeRetriever([mixed]),
        ScriptedModel("El sueldo base del puesto es de €1200 mensuales. [1]"),
    )
    assert ans.abstained and ans.reason == "missing_requested_attribute"


def test_uppercase_euros_amount_is_not_a_headcount() -> None:
    mixed = chunk(
        14,
        "Ayuntamiento de Torrox",
        "El sueldo base del puesto es de 1200 EUROS mensuales. "
        "Se convocan ocho plazas de Subalterno/a, turno libre.",
    )
    ans = answer_question(
        ONE_Q,
        FakeRetriever([mixed]),
        ScriptedModel("El sueldo base del puesto es de 1200 EUROS mensuales. [1]"),
    )
    assert ans.abstained and ans.reason == "missing_requested_attribute"
