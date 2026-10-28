# ADR-0008: Package layout

- Status: accepted, supersedes ADR-0004
- Date: 2026-10-28

## Context

ADR-0004 chose flat files at the repository root while the project had fewer than ten modules, and said a package would need its own ADR. The new direction (ADR-0005) brings parsers per language, stack detection, layout, rendering, export and a desktop app: around twenty modules.

## Decision

- Source code lives in the `repo_xray` package, grouped by step: `parsers/`, `analysis/`, `render/`, `export/`, `ai/` and `app/`.
- Tests live in `tests/`, mirroring the package.
- Each step still writes plain data that the next step reads (scan → parse → analyse → render → export), as in ADR-0004.

## Consequences

- Imports become `from repo_xray.parsers import java`.
- PyInstaller packages a single entry point, `repo_xray/__main__.py`.
