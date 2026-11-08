# ADR 0004: Rarity-weighted sentence scoring was tried and rejected

Status: rejected (2026-11-08)

Two documented failures (s08, s09, and the original p08/p09) come from the extractive model quoting a boilerplate sentence ("Formentera, 29 de octubre de 2026.–El Presidente...") instead of the sentence that names the position. Hypothesis: the model scores sentences by raw stem overlap, so terms shared by the whole notice (the council's name, "convocatoria") win. Experiment: weight each question stem by 1 / (number of sentences containing it) across the retrieved passages.

Result, same corpus, same two evaluation sets: **every metric identical** on all 58 questions, including the failing cases. Nothing improved and nothing regressed. The change was reverted rather than kept as dead complexity.

Why it could not work: in the failing notices the correct sentence ("Una plaza de Técnico/a de Cultura, perteneciente a la escala...") shares only one stem with the question, "plaza", which is the least distinctive term in a call for posts. Rarity weighting then favours sentences containing "convocatoria" or the council name, which are rarer. The signal that identifies the right sentence is structural (it is the item the notice lists), not lexical overlap.

Next options, not done: a model step that reads the question and the candidate sentences (needs a real model and its own evaluation), or a structural rule for list-like notices (risks being tuned to these 11 documents). Either must be measured on a set written before the change.
