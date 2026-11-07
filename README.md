# sovereign-rag

Offline-first question answering over a small public Spanish corpus (BOE open data). Every answer carries source citations; when no passage supports an answer, it abstains.

**What it is today (v0.1):** a small, deterministic, dependency-free pipeline (BOE XML → paragraph chunks → SQLite FTS5/BM25 retrieval → *extractive* answer → citation validation). It runs with no network, no API keys and no model.

**What it is not:** there is **no LLM** and **no semantic/neural retrieval** in this version. The demo "model" copies the best-matching sentence out of a retrieved passage; it cannot paraphrase, reason or combine facts. The `ModelClient` port is where a real local model would plug in (not implemented yet).

## Quickstart

Python 3.12+, standard library only.

```bash
git clone https://github.com/jorgitobg/sovereign-rag
cd sovereign-rag
python -m venv .venv && . .venv/bin/activate
pip install -e .
sovereign-rag-demo          # or: python -m sovereign_rag.demo
sovereign-rag-eval          # or: python -m sovereign_rag.eval
sovereign-rag-demo "¿Cuántas plazas de Subalterno convoca el Ayuntamiento de Torrox?"
```

Development: `pip install -e '.[dev]'`, then `ruff check . && ruff format --check . && pyright && pytest` (coverage gate 85%).

## Demo output

Real output of `python -m sovereign_rag.demo` (deterministic):

```text
Q: ¿Cuántas plazas de Subalterno convoca el Ayuntamiento de Torrox?
A: Turno libre: Subalterno/a 8 plazas [1]
   fuente BOE-A-2026-23041#0: Resolución de 28 de octubre de 2026, del Ayuntamiento de Torrox (Málaga), referente a la convocatoria para proveer varias plazas.
   https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-23041

Q: ¿Cuál es el plazo de presentación de solicitudes en la convocatoria de Borriana?
A: El plazo de presentación de solicitudes será de diez días hábiles a contar desde el siguiente al de la publicación de esta resolución en el «Boletín Oficial del Estado». [1]
   fuente BOE-A-2026-23049#1: Resolución de 29 de octubre de 2026, del Ayuntamiento de Borriana/Burriana (Castellón/Castelló), referente a la convocatoria para proveer varias plazas.
   https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-23049

Q: ¿Cuántos días tienen los interesados para personarse en el recurso 2067/2026?
A: Mediante la presente resolución, esta Secretaría General Técnica procede a dar cumplimiento al trámite de emplazamiento a todos aquellos que se encuentren interesados en aquel procedimiento, disponiendo de un plazo de nueve días, si a su derecho conviene, para personarse en los autos, a contar desde el día siguiente a la publicación de esta resolución, ante el órgano jurisdiccional que lo ordenó, de acuerdo con lo establecido en el artículo 49 de la Ley 29/1998, de 13 de julio, reguladora de la Jurisdicción Contencioso-Administrativa. [1]
   fuente BOE-A-2026-23097#1: Resolución de 30 de octubre de 2026, de la Secretaría General Técnica, por la que se emplaza a las personas interesadas en el recurso contencioso-administrativo 2067/2026, interpuesto ante el Tribunal Superior de Justicia de Madrid, Sala de lo Contencioso-Administrativo, Sección Séptima.
   https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-23097

Q: ¿Cuál es la capital de Francia?
A: Sin evidencia en el corpus para responder a esta pregunta. (motivo: no_evidence)

Q: ¿Cuántas plazas de bombero convoca el Ayuntamiento de Sevilla?
A: Sin evidencia en el corpus para responder a esta pregunta. (motivo: no_evidence)
```

Note the third answer: it is correct but is a whole sentence, not the short span "nine days" — that is the extractive model, not a bug.

## Evaluation

`python -m sovereign_rag.eval` runs 40 hand-written questions (`src/sovereign_rag/data/golden.jsonl`: 26 answerable, 14 out-of-corpus) against the 11 fixture documents. Real output:

```text
cases: 26 answerable, 14 out-of-corpus
hit@1: 26/26 = 100.0%
hit@3: 26/26 = 100.0%
hit@5: 26/26 = 100.0%
answered (answerable): 22/26 = 84.6%
answer contains expected text: 16/26 = 61.5%
all citations point to gold doc: 22/26 = 84.6%
citation validity: 22/22 = 100.0%
abstention (out-of-corpus): 14/14 = 100.0%
failed cases: p02, p07, p08, p09, p14, p16, p17, p18, p19, p25
```

How to read it:
- **hit@k**: a gold document appears in the top-k retrieved chunks. 100% on 11 documents is an easy setting; it says little about larger corpora.
- **answer contains expected text**: the returned sentence contains a hand-chosen substring. 61.5% is the honest figure for a sentence-extracting model; failures are mostly the model picking a boilerplate or title sentence, or questions needing a paraphrase.
- **citation validity**: every emitted citation resolves to an indexed chunk with a verbatim quote and the right URL. This is true by construction of the validator, so 100% is expected, not an accomplishment.
- **abstention (out-of-corpus)**: 14/14 on these questions. The abstention rule (75% of question content terms plus every capitalised name must be in a retrieved passage) was adjusted while looking at this same dataset, so treat it as tuned on it, not as a held-out measurement.

### Synonyms: a failure found by a live run, and the measured fix

A live agent asked this system "¿Cuántos puestos de subalterno ofrece el Ayuntamiento de Torrox?" and got an abstention, because the notice says *plazas*, not *puestos*. `src/sovereign_rag/application/synonyms.py` now holds a small, explicit table (plaza/puesto/vacante, solicitud/instancia, personarse/comparecer, plazo/tiempo) used both to widen the FTS query and to compare stems. Words outside the table match literally, as before.

To measure it without touching the original set, 18 new paraphrased questions were written (`golden_paraphrase.jsonl`: 12 answerable, 6 out-of-corpus). Same corpus, same code except the table:

```text
                                  before    after
answered (answerable)             4/12      12/12
answer contains expected text     3/12      10/12
all citations point to gold doc   4/12      12/12
abstention (out-of-corpus)        5/6       5/6
original 40-question set          unchanged (identical output)
```

What is still wrong, kept visible on purpose:
- `s08`, `s09`: the right document is retrieved and cited, but the extractive model quotes a boilerplate sentence instead of the position name. The original set fails the same way on the same documents (p08, p09).
- `t05`: *"¿Cuánto cobra un Subalterno en el Ayuntamiento de Torrox?"* gets a confident answer about 8 posts instead of an abstention. It failed identically before the table existed. The document has no salary; term coverage is too forgiving for a question that is about a different fact.
- The paraphrase set was written after seeing the failure, by the same author as the table, so it is not an independent measurement. Treat the jump as evidence the mechanism works, not as an accuracy figure.

## How answers are validated

1. Retrieve top-5 chunks with FTS5; keep only passages that cover the question's content terms.
2. No such passage → "Sin evidencia en el corpus", model not called.
3. Otherwise the `ModelClient` must return claims each followed by `[n]`. Unknown markers, uncited text, empty output or a claim not supported by its cited passage are replaced by an abstention with a reason.

## Limitations

- Tiny corpus (11 documents from one BOE issue, 2026-11-03); the evaluation is small and partly tuned on its own questions.
- Lexical retrieval only; no stemming beyond a crude prefix match, a four-group hand-written synonym table (see below), no embeddings in use.
- The extractive model quotes sentences; it does not answer in its own words and can return a sentence that is on topic but does not contain the specific fact asked for.
- Support checking is word overlap, so it catches fabricated or misattributed citations but not subtle meaning errors. Citations prove *where* text came from, not that the answer is right.
- Not legal advice. BOE texts are reused under the BOE reuse licence; see `tests/fixtures/boe/SOURCES.md`.

## Layout

`domain/` (types, ports) · `application/` (ingest, answer policy) · `adapters/` (BOE XML, FTS5, hashing embedder, extractive model) · `demo.py`, `eval.py` · spec in `docs/spec/`, decisions in `docs/adr/`.

Licence: Apache-2.0.
