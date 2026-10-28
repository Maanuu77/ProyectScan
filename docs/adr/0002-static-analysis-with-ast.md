# ADR-0002: Static analysis with the standard `ast` module

- Status: accepted
- Date: 2026-10-28

## Context

We need the modules, classes, functions, imports and calls of a Python project. Options:

- Import the project and inspect it at runtime: executes untrusted code and needs its dependencies installed.
- `ast` from the standard library: parses source without running it.
- `tree-sitter`: multi-language, but an extra native dependency and a lower-level tree.
- Tools such as `jedi` or `pyright`: precise name resolution, but heavy and harder to explain.

## Decision

Use `ast`. Parse each file on its own and never import or execute the analysed project.

## Consequences

- Safe on any repository and no dependencies needed for the analysis.
- Name resolution is approximate: a call is resolved only within its file and through direct imports, and anything else is marked as "probable". This limitation is documented, not hidden.
- Supporting other languages later means adding `tree-sitter` behind the same data model.
