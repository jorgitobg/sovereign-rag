"""Ports (ADR 0001). Adapters implement them; the application depends only on these."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .models import Chunk, Hit


class Retriever(Protocol):
    def index(self, chunks: Sequence[Chunk]) -> None: ...

    def search(self, query: str, k: int = 5) -> list[Hit]: ...


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class ModelClient(Protocol):
    """Turns a question plus numbered passages into text that cites passages as ``[n]``.

    ``passages[0]`` is ``[1]``. Implementations may be extractive, scripted or an LLM; the
    application validates every citation, so an implementation cannot smuggle in unsupported
    claims.
    """

    def answer(self, question: str, passages: Sequence[Chunk]) -> str: ...
