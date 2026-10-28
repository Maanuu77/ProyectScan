# Roadmap · repo-xray

repo-xray scans a Python project, builds an interactive graph of its files, classes and functions, and explains each node with a local LLM (Ollama). Everything runs offline and free.

Each issue below has a number (`#n`) that branches and commits reference. Status: ✅ done · 🚧 in progress · ⬜ pending.

## Sprint 0 · Foundations

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #1 | Roadmap with sprint backlog | `docs/roadmap` | ✅ |
| #2 | Project setup: `.gitignore`, `.gitattributes`, dev requirements, pytest config | `chore/project-setup` | ⬜ |
| #3 | ADR process and initial architecture decisions | `docs/adr` | ⬜ |

## Sprint 1 · Scanner and static analysis

Done when `python main.py <path>` prints a correct summary of a real project.

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #4 | Configuration module with defaults and optional `xray.toml` | `feature/backend-scanner` | ⬜ |
| #5 | Scanner: walk a folder, skip `.git`, virtualenvs, caches and hidden dirs | `feature/backend-scanner` | ⬜ |
| #6 | Analyzer: extract modules, classes, functions and methods with `ast` | `feature/backend-analyzer` | ⬜ |
| #7 | Analyzer: extract imports (absolute and relative) | `feature/backend-analyzer` | ⬜ |
| #8 | Analyzer: extract calls with their enclosing scope | `feature/backend-analyzer` | ⬜ |
| #9 | Analyzer: survive files with syntax or encoding errors | `feature/backend-analyzer` | ⬜ |
| #10 | Export the analysis to JSON | `feature/backend-cli` | ⬜ |
| #11 | CLI entry point that prints a project summary | `feature/backend-cli` | ⬜ |

## Sprint 2 · Dependency graph

Done when nodes and edges exported to JSON match what you see in the code.

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #12 | Build a `networkx` graph with file, class and function nodes and `contains` edges | `feature/backend-graph` | ⬜ |
| #13 | Resolve imports to project modules (`imports` edges) | `feature/backend-graph` | ⬜ |
| #14 | Resolve calls inside the same file and through direct imports; mark the rest as probable | `feature/backend-call-resolution` | ⬜ |
| #15 | Inheritance edges (`inherits`) | `feature/backend-call-resolution` | ⬜ |
| #16 | Export graph nodes and edges to JSON | `feature/backend-graph` | ⬜ |

## Sprint 3 · Interactive visualization

Done when the page opens in the browser and is smooth to explore.

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #17 | Generate a self-contained HTML graph page | `feature/frontend-graph-view` | ⬜ |
| #18 | Colour by node type, size by number of connections | `feature/frontend-graph-view` | ⬜ |
| #19 | Filters by type and folder, collapsed per-file view, node limit | `feature/frontend-filters` | ⬜ |
| #20 | Side panel with node details and source code | `feature/frontend-side-panel` | ⬜ |

## Sprint 4 · AI explanations

Done when every function gets a short, correct explanation.

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #21 | Ollama client with timeout and clear error when Ollama is not running | `feature/backend-ollama-client` | ⬜ |
| #22 | Explanation prompt that only uses the given code | `feature/backend-explainer` | ⬜ |
| #23 | Explanation cache keyed by the hash of the code | `feature/backend-explainer` | ⬜ |
| #24 | Show explanations in the side panel, labelled "AI-generated" | `feature/frontend-explanations` | ⬜ |

## Sprint 5 · Metrics

Done when the graph highlights the most complex and possibly dead functions.

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #25 | Cyclomatic complexity per function | `feature/backend-metrics` | ⬜ |
| #26 | Possible dead code detection, excluding decorated, `__main__`, test and dunder functions | `feature/backend-metrics` | ⬜ |
| #27 | Warning colours for complexity and dead code in the graph | `feature/frontend-metrics` | ⬜ |

## Sprint 6 · Report and CLI

Done when `python main.py <path> --report` writes the file.

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #28 | Markdown report export | `feature/backend-report` | ⬜ |
| #29 | CLI options: output folder, model, no-AI mode, open browser | `feature/backend-cli-options` | ⬜ |

## Sprint 7 · Polish and release

Done when someone else can install and use it by following the README.

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #30 | GitHub Actions: tests on every push | `ci/tests` | ⬜ |
| #31 | README in English and Spanish, demo GIF, technical decisions | `docs/readme` | ⬜ |
| #32 | Release 1.0.0: `CHANGELOG.md`, tag `v1.0.0` | `release/1.0.0` | ⬜ |

## After 1.0.0

- Java and JavaScript support with `tree-sitter` (demo: analyse Benchify).
- Compare the graph of two commits.
- Export the diagram to Mermaid.
- "Explain this repository" mode with an architecture summary.
