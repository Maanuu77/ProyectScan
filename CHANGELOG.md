# Changelog

All notable changes to repo-xray. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## 1.0.1 - 2026-10-28

### Fixed

- The app could close without warning when a new task started just as the previous one finished, for example exporting right after an analysis or changing the language quickly: a background thread was destroyed while it was still stopping.
- The CI smoke test now waits for the executable to finish before checking its zip, so the 1.0.0 release, which never published its executable, is replaced by this one.

## 1.0.0 - 2026-10-28

First release: a desktop app and a command line that turn a project's source code into architecture documentation in three levels.

### Added

- **Languages.** Python with `ast`; Java and TypeScript/JavaScript with tree-sitter, into one language-neutral model. Broken files are reported and the rest of the project is still analysed.
- **Level 1, overview.** Apps, their technologies and versions, databases and external services, deployment targets and CI, detected from build manifests, dependencies, imports, `compose.yaml`, `firebase.json`, connection strings and cloud files.
- **Level 2, features.** Features found from container folders, vertical slices or shared names; files classified into entry, application, domain, data and integration layers; frontend features linked to the backend features they call.
- **Level 3, flows.** Spring endpoints, frontend HTTP calls (`HttpClient`, `fetch`, `axios`) linked to them by route, and calls resolved through fields, imports and interfaces, from the screen to the database.
- **Diagrams.** SVG in light and dark versions with GitHub's palette, text measured to fit its box, and PNG copies.
- **Export.** A zip with Markdown pages (an index and one page per feature), the diagrams, the raw analysis as JSON, a `HOW-TO-USE.md` guide and a snippet for the project's README.
- **Texts without AI.** Descriptions from the project's README and manifests, OpenAPI tags, Javadoc and route titles; generated sentences for undocumented features; documents in English or Spanish, following the code.
- **Desktop app.** Drag a folder or choose it, follow the progress, preview diagrams and pages in light or dark, choose the language, edit names and descriptions (saved in `xray.toml`) and export the zip.
- **Windows executable.** A single `repo-xray.exe` with its own icon and no console window.
- **CI.** Tests on Windows and Linux and a smoke-tested executable on every push; releases publish the executable.
- **License.** MIT.

### Fixed during development

- Folders named `out`, `bin` or `obj`, such as hexagonal `port/out` packages, are no longer skipped.
- Projects deeper than 260 characters no longer stop the analysis on Windows.
- A workspace `package.json` at the root no longer becomes an empty app.
- An app whose code lives entirely in `features/` is split into its features.
- Route titles lose the app's name even when the folder is named differently.

