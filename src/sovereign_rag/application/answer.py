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

    text = model.answer(question, passages).strip()
    if not text:
        return _abstain("empty_output")
    markers = list(_MARKER.finditer(text))
    if not markers:
        return _abstain("uncited_output")
    if _MARKER.sub("", text[markers[-1].end() :]).strip():
        return _abstain("uncited_output")  # trailing claim with no marker
    citations: list[Citation] = []
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
        citations.append(
            Citation(chunk.id, chunk.doc_id, chunk.title, chunk.url, claim, _quote(chunk))
        )
    return Answer(text, tuple(citations), False)
