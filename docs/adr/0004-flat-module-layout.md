# ADR-0004: Flat module layout and separate analysis and rendering

- Status: superseded by ADR-0008
- Date: 2026-10-28

## Context

The project is small (around ten modules) and is read by people reviewing a portfolio. A deep package structure would add navigation without adding clarity.

## Decision

- Keep every module and test as a flat file at the repository root (`scanner.py`, `analyzer.py`, `test_analyzer.py`…). Documentation lives in `docs/`.
- Each step writes plain data that the next step reads: scanner → analyzer → graph → viewer. The analysis can be exported to JSON, so analysing and displaying can be debugged separately.
- Code, identifiers and commits are in English; the README is bilingual.

## Consequences

- Easy to follow from the repository's front page.
- If the project grows well beyond ten modules, it should move into a package; that would be a new ADR.
