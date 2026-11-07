# ADR 0003: Explicit synonym table instead of embeddings

Status: accepted (2026-11-07)

A live agent hit an abstention because the corpus says "plazas" and the user said "puestos". Options: a neural embedder (semantic, but adds a model download, non-determinism and a harder-to-explain failure mode), automatic query expansion with a thesaurus (opaque, can over-match), or a short hand-written table.

Decision: the table. It is four groups, readable in ten seconds, deterministic, auditable in review, and every entry can be justified from a real notice. It is applied in two places on purpose: the FTS query (so the right chunk is retrieved) and the stem comparison (so the coverage and support checks do not reject it).

Consequences: it fixes the observed class of miss and nothing else. It cannot generalise to words nobody listed, and a wrong entry would silently widen matches, so the table has a uniqueness test and a regression floor on a paraphrase set. The hashing embedder and a real embedder remain the path for broader semantics, with the same evaluation deciding whether they help.
