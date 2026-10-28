# Roadmap · repo-xray

repo-xray is a desktop app that scans a software project and generates clear, good-looking architecture documentation: SVG diagrams plus Markdown pages, delivered as a zip that the user can drop into their repository. It understands Python, Java and TypeScript, explains the project in three levels and can use a local LLM (Ollama) for the wording. Everything runs offline and free.

The direction changed after sprint 1 (see [ADR-0005](adr/0005-architecture-docs-in-three-levels.md)). Issues #1-#11 keep their numbers; the old pending issues #12-#32 were replaced by the backlog below.

Status: ✅ done · 🚧 in progress · ⬜ pending.

## The three levels

1. **Overview** · "What is it made of?" Apps, databases, external services and deployment, mostly detected from manifests (`pom.xml`, `package.json`, `Dockerfile`, `compose.yaml`, `firebase.json`, CI workflows…).
2. **Features** · "What does it do?" One card per business feature with a one-line description and the layers it touches.
3. **Flows** · "What happens when…?" The path of a request from the frontend through the backend to the database, linking HTTP calls in the frontend to the endpoints that serve them.

Plus one detail page per feature. Each diagram shows at most ~9 elements; anything beyond that goes one level deeper.

## Sprint 0 · Foundations

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #1 | Roadmap with sprint backlog | `docs/roadmap` | ✅ |
| #2 | Project setup: `.gitignore`, `.gitattributes`, dev requirements, pytest config | `chore/project-setup` | ✅ |
| #3 | ADR process and initial architecture decisions | `docs/adr` | ✅ |

## Sprint 1 · Scanner and Python analysis

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #4 | Configuration module with defaults and optional `xray.toml` | `feature/backend-scanner` | ✅ |
| #5 | Scanner: walk a folder, skip `.git`, virtualenvs, caches and hidden dirs | `feature/backend-scanner` | ✅ |
| #6 | Analyzer: extract modules, classes, functions and methods with `ast` | `feature/backend-analyzer` | ✅ |
| #7 | Analyzer: extract imports (absolute and relative) | `feature/backend-analyzer` | ✅ |
| #8 | Analyzer: extract calls with their enclosing scope | `feature/backend-analyzer` | ✅ |
| #9 | Analyzer: survive files with syntax or encoding errors | `feature/backend-analyzer` | ✅ |
| #10 | Export the analysis to JSON | `feature/backend-cli` | ✅ |
| #11 | CLI entry point that prints a project summary | `feature/backend-cli` | ✅ |

## Sprint 2 · New direction and multi-language foundation

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #12 | Rewrite roadmap and record the new direction in ADRs | `docs/replan` | ✅ |
| #13 | Move to a `repo_xray` package with a `tests` folder | `refactor/package-layout` | ✅ |
| #14 | Language-neutral model: files, symbols, imports, calls, endpoints, HTTP calls | `refactor/language-model` | ✅ |
| #15 | Scanner: all supported languages, skip generated folders (`target`, `coverage`, `.angular`…) | `refactor/language-model` | ✅ |

## Sprint 3 · Java and TypeScript

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #16 | Java parser with tree-sitter: package, types, methods, annotations, imports, calls | `feature/backend-java-parser` | ✅ |
| #17 | Spring endpoints from `@*Mapping` annotations | `feature/backend-java-parser` | ✅ |
| #18 | TypeScript parser: classes, functions, imports, calls, Angular decorators | `feature/backend-typescript-parser` | ✅ |
| #19 | HTTP calls in the frontend (`HttpClient`, `fetch`, `axios`) | `feature/backend-typescript-parser` | ✅ |

## Sprint 4 · Level 1 · Overview

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #20 | Detect apps (containers) and their tech stack from manifests | `feature/backend-stack-detection` | ✅ |
| #21 | Detect databases, external services and deployment targets | `feature/backend-stack-detection` | ✅ |
| #22 | SVG design system: theme tokens, light and dark variants, text measurement | `feature/frontend-svg-theme` | ✅ |
| #23 | Overview diagram renderer | `feature/frontend-overview-diagram` | ✅ |

## Sprint 5 · Level 2 · Features

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #24 | Classify files into layers (entry, application, domain, infrastructure, shared, tests) | `feature/backend-layers` | ✅ |
| #25 | Detect features from feature folders, or by clustering names in layer-first projects | `feature/backend-features` | ✅ |
| #26 | Match frontend features to backend features | `feature/backend-features` | ✅ |
| #27 | Feature map diagram renderer | `feature/frontend-feature-diagram` | ⬜ |

## Sprint 6 · Level 3 · Flows

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #28 | Link frontend HTTP calls to backend endpoints by route | `feature/backend-http-linking` | ✅ |
| #29 | Build flows: UI → frontend service → endpoint → use case → repository → storage | `feature/backend-flows` | 🚧 |
| #30 | Pick the most representative flows | `feature/backend-flows` | ⬜ |
| #31 | Flow diagram renderer (swimlanes) | `feature/frontend-flow-diagram` | ⬜ |

## Sprint 7 · Local AI

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #32 | Ollama client: detection, model check, timeout | `feature/backend-ollama-client` | ⬜ |
| #33 | Feature names and one-line descriptions, with validation against real names | `feature/backend-ai-descriptions` | ⬜ |
| #34 | Architecture summary paragraph and flow titles | `feature/backend-ai-descriptions` | ⬜ |
| #35 | Cache by content hash and user overrides in `xray.toml` | `feature/backend-ai-descriptions` | ⬜ |

## Sprint 8 · Export

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #36 | Markdown pages: index with the three levels and one page per feature | `feature/backend-markdown-export` | ⬜ |
| #37 | PNG copies of every diagram | `feature/backend-png-export` | ⬜ |
| #38 | Zip export with a short "how to use these files" note | `feature/backend-zip-export` | ⬜ |

## Sprint 9 · Desktop app

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #39 | Main window: choose a folder, analyse in the background with progress | `feature/frontend-desktop-app` | ⬜ |
| #40 | Preview of the diagrams and pages, light and dark | `feature/frontend-desktop-app` | ⬜ |
| #41 | Export the zip from the app | `feature/frontend-desktop-app` | ⬜ |
| #42 | AI setup assistant: detect Ollama, guide its installation, download the model with progress | `feature/frontend-ai-setup` | ⬜ |

## Sprint 10 · Packaging and release

| # | Issue | Branch | Status |
| --- | --- | --- | --- |
| #43 | Windows executable with PyInstaller | `chore/packaging` | ⬜ |
| #44 | GitHub Actions: tests on every push, executable on tags | `ci/tests-and-build` | ⬜ |
| #45 | README in English and Spanish with screenshots and repo-xray's own diagrams | `docs/readme` | ⬜ |
| #46 | Release 1.0.0: `CHANGELOG.md`, tag `v1.0.0` | `release/1.0.0` | ⬜ |

## After 1.0.0

- GitHub Action that regenerates the docs on every push.
- macOS and Linux builds.
- More languages (Kotlin, C#, Go).
