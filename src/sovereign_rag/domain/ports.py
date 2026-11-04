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
