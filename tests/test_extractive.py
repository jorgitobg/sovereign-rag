from datetime import date

from sovereign_rag.adapters.extractive import ExtractiveModel, split_sentences
from sovereign_rag.domain.models import Chunk
from sovereign_rag.domain.ports import ModelClient


def chunk(i: int, text: str, title: str = "Ayuntamiento") -> Chunk:
    return Chunk(f"D{i}#0", f"D{i}", title, "Dep", date(2026, 1, 1), "u", text)


def test_split_sentences_keeps_decimals_and_article_numbers() -> None:
    parts = split_sentences("Importe: 79.388,68 euros. Ver art. 3 de la Ley. Segunda frase.")
    assert parts == ["Importe: 79.388,68 euros.", "Ver art. 3 de la Ley.", "Segunda frase."]


def test_paragraph_boundaries_are_sentence_boundaries() -> None:
    assert split_sentences("Bases en el boletín núm. 167\nOcho plazas de Subalterno") == [
        "Bases en el boletín núm. 167",
        "Ocho plazas de Subalterno",
    ]


def test_picks_best_overlapping_sentence_and_cites_it() -> None:
    m: ModelClient = ExtractiveModel()
    text = "Ocho plazas de Subalterno. El plazo de presentación de solicitudes es de veinte días."
    out = m.answer("plazo de presentación de solicitudes", [chunk(1, text)])
    assert out == "El plazo de presentación de solicitudes es de veinte días. [1]"


def test_cites_the_passage_the_sentence_came_from() -> None:
    out = ExtractiveModel().answer(
        "plazas de policía local",
        [
            chunk(1, "Texto sin relación alguna."),
            chunk(2, "Nueve plazas de Agente de la policía local."),
        ],
    )
    assert out.endswith("[2]") and "policía local" in out


def test_title_terms_break_ties_between_boilerplate_sentences() -> None:
    a = chunk(1, "El plazo de solicitudes es de diez días.", "Ayuntamiento de Borriana")
    b = chunk(2, "El plazo de solicitudes es de veinte días.", "Ayuntamiento de Torrox")
    out = ExtractiveModel().answer("plazo de solicitudes de Torrox", [a, b])
    assert out == "El plazo de solicitudes es de veinte días. [2]"


def test_returns_empty_when_nothing_overlaps() -> None:
    assert ExtractiveModel().answer("hipoteca", [chunk(1, "Plazas de subalterno.")]) == ""
    assert ExtractiveModel().answer("plazas", []) == ""
    assert ExtractiveModel().answer("¿Cuántas?", [chunk(1, "Plazas.")]) == ""


def test_is_deterministic_and_limits_sentences() -> None:
    ps = [chunk(i, f"Plazas número {i} del cuerpo.") for i in range(1, 5)]
    a = ExtractiveModel(max_sentences=2).answer("plazas cuerpo", ps)
    assert a == ExtractiveModel(max_sentences=2).answer("plazas cuerpo", ps)
    assert a.count("[") == 2
