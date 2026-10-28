# ADR-0009: The local AI is optional

- Status: superseded by ADR-0011
- Date: 2026-10-28

## Context

ADR-0003 chose Ollama for explanations. With a desktop app for beginners (ADR-0006), requiring Ollama before anything works would block most first-time users. Bundling a model inside the executable would add several gigabytes.

## Decision

- Every diagram and page is generated without AI. Feature names come from folders and code names, descriptions from docstrings and Javadoc, and layers from rules.
- When Ollama is running, the app uses it to improve names and descriptions, write the architecture summary and title the flows.
- The app includes an assistant that detects Ollama, links to its installer and downloads the model with a progress bar.
- AI output is cached by content hash, checked against the real names in the code, and can be overridden by the user in `xray.toml`.

## Consequences

- The app works on the first run, with no setup.
- Quality without AI depends on how well the project is named; the results must still be useful.
- Two paths to test: with and without AI.
