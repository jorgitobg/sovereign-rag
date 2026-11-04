"""Deterministic hashing-trick embedder (ADR 0002). No model, no download."""

from __future__ import annotations

import hashlib
import itertools
import math

from .fts5 import query_terms


class HashingEmbedder:
    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        terms = query_terms(text)
        # unigrams + bigrams give a little word-order signal
        feats = terms + [f"{a}_{b}" for a, b in itertools.pairwise(terms)]
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            vec[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec
