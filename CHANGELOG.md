# Changelog

## 0.1.0

Changes since v0.0.1 (2 commits on main; see `git log v0.0.1..v0.1.0`).

### Fixed
- The pipeline now abstains when the question asks for an attribute (for example pay) and no retrieved passage carries a matching marker, instead of returning a cited answer that does not address it. New tests cover this; design notes in ADR 0005.

### Changed
- CI actions moved to current major versions.

### Known limits
- Requested-attribute checks are finite lexical guards, not entailment. Prefix collisions remain (the pay marker `comple` matches both `complemento` and `completa`), so a count-only statement can still pass a pay-marker check.
- Tiny corpus (11 BOE documents), lexical retrieval only, extractive answers, no LLM. See the README.
