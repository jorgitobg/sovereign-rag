"""US3: cited answers or an honest abstention.

Policy (spec 0001): the model is only called when retrieved passages cover the question; its
output is returned only if every claim is followed by ``[n]`` markers that resolve to a passage
that lexically supports the claim. Anything else becomes an abstention with a reason.
"""

from __future__ import annotations

import re

from sovereign_rag.adapters.fts5 import fold, query_terms
from sovereign_rag.application.synonyms import canonical
from sovereign_rag.domain.models import Answer, Chunk, Citation
from sovereign_rag.domain.ports import ModelClient, Retriever

ABSTENTION_TEXT = "Sin evidencia en el corpus para responder a esta pregunta."
MIN_COVERAGE = 0.75  # share of question content stems a passage must contain to count as evidence
MIN_CLAIM_SUPPORT = 0.5  # share of a claim's content stems that must appear in its cited passage
QUOTE_CHARS = 240

_QUESTION_WORDS = frozenset(
    {
        "cual", "cuales", "cuanto", "cuanta", "cuantos", "cuantas",
        "como", "donde", "quien", "quienes", "cuando", "que", "cuesta",
    }
)  # fmt: skip
_MARKER = re.compile(r"\[(\d+)\]")


def stems(text: str) -> set[str]:
    """Crude Spanish normalisation: drop plural -s, map listed synonyms, keep a 6-letter prefix."""
    out: set[str] = set()
    for t in query_terms(text):
        if t in _QUESTION_WORDS:
            continue
        t = t[:-1] if len(t) > 3 and t.endswith("s") else t
        out.add(canonical(t)[:6])
    return out


def proper_nouns(question: str) -> set[str]:
    """Capitalised words after the first token (places, institutions): all must be in a passage."""
    words = re.findall(r"\w+", question)[1:]
    return {w for w in words if w[0].isupper() and len(w) > 2 and fold(w) not in _QUESTION_WORDS}


def passage_stems(chunk: Chunk) -> set[str]:
    return stems(f"{chunk.title} {chunk.text}")


def _abstain(reason: str) -> Answer:
    return Answer(ABSTENTION_TEXT, (), True, reason)


def _quote(chunk: Chunk) -> str:
    text = chunk.text
    return text if len(text) <= QUOTE_CHARS else text[:QUOTE_CHARS].rstrip() + "…"


def answer_question(
    question: str,
    retriever: Retriever,
    model: ModelClient,
    *,
    k: int = 5,
    max_passages: int = 3,
) -> Answer:
    q = stems(question)
    if not q:
        return _abstain("no_evidence")
    names = [s for s in (stems(w) for w in sorted(proper_nouns(question))) if s]
    passages: list[Chunk] = []
    for hit in retriever.search(question, k):
        have = passage_stems(hit.chunk)
        covered = len(q & have)
        if covered >= MIN_COVERAGE * len(q) and all(n <= have for n in names):
            passages.append(hit.chunk)
        if len(passages) == max_passages:
            break
    if not passages:
        return _abstain("no_evidence")

    wanted = _attribute(question)
    if wanted and not any(_body_has_evidence(wanted, c) for c in passages):
        return _abstain("missing_requested_attribute")  # before invoking the model

    text = model.answer(question, passages).strip()
    if not text:
        return _abstain("empty_output")
    markers = list(_MARKER.finditer(text))
    if not markers:
        return _abstain("uncited_output")
    if _MARKER.sub("", text[markers[-1].end() :]).strip():
        return _abstain("uncited_output")  # trailing claim with no marker
    citations: list[Citation] = []
    evidenced = not wanted
    start = 0
    for m in markers:
        n = int(m.group(1))
        if not 1 <= n <= len(passages):
            return _abstain("invalid_citation")
        claim = _MARKER.sub("", text[start : m.start()]).strip()
        start = m.end()
        chunk = passages[n - 1]
        cs = stems(claim)
        if not cs or len(cs & passage_stems(chunk)) < MIN_CLAIM_SUPPORT * len(cs):
            return _abstain("unsupported_claim")
        if _has_evidence(wanted, claim, cs):
            evidenced = True
        citations.append(
            Citation(chunk.id, chunk.doc_id, chunk.title, chunk.url, claim, _quote(chunk))
        )
    if not evidenced:
        return _abstain("missing_requested_attribute")
    return Answer(text, tuple(citations), False)


# --- S05: explicit requested-attribute evidence (finite, hand-written; no ontology) ---
# Detects what fact the question asks *for* (salary / deadline / quantity of posts) and
# requires the cited claim itself to contain evidence of that fact, not merely overlap.
# Deliberately finite: paraphrases outside these word lists get no extra protection.

# Stems here are the exact 6-character prefixes `stems()` produces for the advertised
# words (e.g. "sueldo" -> "sueldo", not "sueld"); `tiempo` folds to canonical "plazo".
_SALARY_INTENT = frozenset({"cobra", "sueldo", "salari", "retrib", "remune"})
_SALARY_EVIDENCE = frozenset({"sueldo", "salari", "retrib", "remune", "comple"})
_DEADLINE_INTENT = frozenset({"plazo"})
_DEADLINE_EVIDENCE = frozenset({"plazo", "dia", "mes", "habil", "habile", "natura", "naturale"})
_COUNT_NOUNS = frozenset({"plaza", "puesto", "vacant"})
_CARDINALS = frozenset(
    {
        "un", "uno", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
        "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciseis",
        "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidos",
        "veintitres", "veinticuatro", "veinticinco", "treinta", "cuarenta", "cincuenta",
        "sesenta", "setenta", "ochenta", "noventa", "cien",
    }
)  # fmt: skip
_MONEY = re.compile(r"\d[\d.,]*\s*(?:euros|€)|€\s*\d[\d.,]*", re.IGNORECASE)


def _body_has_evidence(attribute: str, chunk: Chunk) -> bool:
    """Conservative prefilter on the passage *body* (never the title); salary/deadline only."""
    if attribute not in ("salary", "deadline"):
        return True
    return _has_evidence(attribute, chunk.text, stems(chunk.text))


def _attribute(question: str) -> str:
    """The requested fact class, or ``""`` when no explicit rule matches."""
    q = stems(question)
    if q & _SALARY_INTENT:
        return "salary"
    if q & _DEADLINE_INTENT:
        return "deadline"
    if "cuant" in fold(question) and q & _COUNT_NOUNS:
        return "quantity"
    return ""


def _has_evidence(attribute: str, claim: str, claim_stems: set[str]) -> bool:
    if attribute == "salary":
        return bool(claim_stems & _SALARY_EVIDENCE) or bool(_MONEY.search(claim))
    if attribute == "deadline":
        return bool(claim_stems & _DEADLINE_EVIDENCE)
    if attribute == "quantity":
        # Cardinal words are matched on the raw tokens so retrieval stopwords ("un",
        # "una") cannot erase them; only digits *inside a monetary amount*
        # (e.g. "1.200 euros") are excluded from the digit check.
        if any(t in _CARDINALS for t in re.findall(r"\w+", fold(claim))):
            return True
        return any(ch.isdigit() for ch in _MONEY.sub(" ", claim))
    return True
