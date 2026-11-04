"""Deterministic extractive ModelClient: quotes the best-matching sentence. No LLM, no network.

It cannot paraphrase, reason or combine facts; it copies a sentence from a passage and cites it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from sovereign_rag.application.answer import stems
from sovereign_rag.domain.models import Chunk

_SENTENCE_END = re.compile(r"\n+|(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ«¿¡])")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


class ExtractiveModel:
    def __init__(self, max_sentences: int = 1) -> None:
        self.max_sentences = max_sentences

    def answer(self, question: str, passages: Sequence[Chunk]) -> str:
        q = stems(question)
        scored: list[tuple[int, int, int, int, str]] = []
        for n, chunk in enumerate(passages, start=1):
            title_overlap = len(q & stems(chunk.title))
            for pos, sentence in enumerate(split_sentences(chunk.text)):
                overlap = len(q & stems(sentence))
                if overlap:
                    scored.append((-overlap, -title_overlap, n, pos, sentence))
        if not scored:
            return ""
        scored.sort()
        seen: set[str] = set()
        parts: list[str] = []
        for _, _, n, _, sentence in scored:
            if sentence in seen:
                continue
            seen.add(sentence)
            parts.append(f"{sentence} [{n}]")
            if len(parts) == self.max_sentences:
                break
        return " ".join(parts)
