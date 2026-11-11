# ADR 0005: explicit requested-attribute evidence checks

Date: 2026-11-11 · Status: accepted

## Context

The paraphrase set exposed `t05` ("¿Cuánto cobra un Subalterno en el Ayuntamiento de Torrox?"):
the document is about 8 posts and has no salary, yet coverage + claim-overlap accepted a cited
answer about headcount. Lexical overlap identifies related terms in a cited passage; it does
not prove that a claim is entailed by that passage or addresses the requested fact.

## Decision

A small, hand-written requested-attribute policy in `application/answer.py` (no model, no
ontology, no question blacklist, no threshold retuning, no blanket refusal of numeric
questions):

- Detect one of three intent classes from the question with finite word lists:
  salary/pay (`cobra`, `sueldo`, `salario`, `retribución`, `remuneración`),
  deadline/time (`plazo`, `tiempo`), and quantity of posts (`cuant*` plus
  `plaza`/`puesto`/`vacante`). Anything else stays on the old behaviour.
- When detected, at least one cited claim must itself contain evidence of the requested
  fact: salary = a pay stem or a monetary amount; deadline = a day/period term
  (`plazo`, `día`, `mes`, `hábil`, `natural`, `tiempo`); quantity = a digit or Spanish
  cardinal word, with digits inside monetary amounts explicitly not counting as headcounts.
  Missing evidence abstains with reason `missing_requested_attribute`.
- Evidence markers are checked on claim text after the existing citation and lexical-support
  validation (the latter still compares against title plus body). A single-claim response
  lacking the selected attribute's markers is refused even if another source sentence has
  those markers. This is not a claim of semantic entailment or per-claim body verification.
- Round 2 (same day, after review): the stem constants were audited against the actual
  six-character normaliser — `sueldo` normalises to `sueldo`, not `sueld`, so the advertised
  salary word silently matched nothing; `sueld` became `sueldo` in intent and evidence, dead
  `tiemp` entries were dropped (`tiempo` folds to canonical `plazo`), and the singular forms
  `habil`/`natura` joined their plurals. Quantity evidence no longer depends on retrieval
  stopwords: cardinal words are matched on the raw claim tokens, so "una plaza" counts, and
  the digit check strips only digits *inside* monetary amounts, so a claim stating both
  "8 plazas" and "1200 euros" stays answerable while an amount-only claim still abstains.
  A conservative body prefilter abstains before the model is invoked when no retrieved
  passage *body* (title excluded) contains salary or deadline evidence; quantity is exempt
  because headcount and amount legitimately co-occur.

## TDD evidence

Vertical slices, RED first:

- Salary slice: regression with a count-only passage and the extractive-style reply failed
  (answer accepted) before the check existed; positive salary-evidence case added.
- Deadline slice: wrong-fact regression (deadline asked, count sentence cited) failed before
  the check; positive deadline case added.
- Quantity slice: wrong-fact regression (headcount asked, salary sentence with "1.200 euros"
  cited) initially passed because any digit counted; the monetary-amount exclusion made it
  RED, then GREEN.
- One existing test input was adjusted, transparently: the quote-truncation test's reply
  ("Plazas de Subalterno. [1]") carried no number, so the new quantity rule correctly
  abstains; its reply now reads "Ocho plazas de Subalterno. [1]" and the truncation assertion
  is unchanged.
- Monetary-format regressions: a salary-only claim using `€1200` or `1200 EUROS` was
  incorrectly accepted as headcount evidence. Each new end-to-end test failed before its
  minimal fix: consume the complete prefix amount, then make currency matching case-insensitive.

## Evaluation (real CLI output, sets unchanged)

```text
                                  before   after
original 40-question set          22/26 answered, 16/26 expected-text,
                                  22/26 gold-doc, 14/14 abstention   (identical)
paraphrase 18-case set            answered 12/12 (same), expected-text 10/12 (same),
                                  gold-doc 12/12 (same), abstention 5/6 -> 6/6 (t05 fixed)
```

Known retained failures (`p02, p07, p08, p09, p14, p16, p17, p18, p19, p25` original;
`s08, s09` paraphrase) are unchanged extractive-selection issues, not abstention regressions.

## Known limitations

- The vocabulary is finite and hand-written: requests using only outside-vocabulary words
  (`emolumentos`, `hasta el día X`, foreign words) get no extra protection. `sueldo bruto`
  is recognised because `sueldo` is listed. Cardinal matching is token-exact, not a numeric
  parser: compound forms are not interpreted, although a matching component can make the
  check pass. Any bare digit or listed cardinal may refer to a year, identifier or an
  unrelated quantity rather than a headcount. A monetary amount can be a fee rather than
  a salary. The guards do not establish which entity or attribute a value belongs to.
  The salary/deadline prefilter refuses without calling the model when none of the eligible
  passage bodies contain the selected attribute's markers; it does not prove a fact exists.
- The pay-evidence prefix `comple` is intended to match `complemento` (a pay component),
  but also matches non-pay words such as `completa`. Such prefix collisions can make a
  count-only statement appear to contain a pay marker. This is a known lexical false positive,
  not a guarantee of reliable salary detection.
- Semantic entailment is out of scope: negation, paraphrase and numeric reasoning errors are
  not caught. Citations still prove provenance, not truth.
- The evidence check is answer-level (one evidenced claim suffices); a multi-claim answer
  mixing an evidenced and an unevidenced claim about the same attribute is accepted.
- Intent detection is heuristic; a genuine deadline question phrased without `plazo`/`tiempo`
  (e.g. "¿Hasta cuándo…?") is not covered.
- Semantic entailment on the passage body remains out of scope: the prefilter is a finite
  word/amount check, not an entailment test. Evaluation metrics are unchanged by round 2
  (original 22/26 answered, 16/26 expected-text, 14/14 abstention; paraphrase 12/12
  answered, 10/12 expected-text, 6/6 abstention).
