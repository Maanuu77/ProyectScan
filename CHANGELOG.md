# Changelog

All notable changes to repo-xray. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

The product redesign: a new app, a new visual language for the diagrams and an analysis that says where it is and what it could not do. Existing `xray.toml` files, the command line and the layout of the exported zip are unchanged.

### Added

- **App: navigation by level.** A sidebar lists every document under Overview, Features and Flows, with a filter by name, description or route. Every drawn flow can be reached; 1.0 listed three. Tabs and `Ctrl+1`, `Ctrl+2`, `Ctrl+3` jump between levels.
- **App: diagrams you can move in.** Zoom around the pointer, pan by dragging, fit the width or the whole diagram, find text in the diagram (`Ctrl+F`) and full screen (`F11`).
- **App: cards that lead somewhere.** A feature's card opens its page, an app opens the feature map, a step of a flow leads to its feature. Pages draw their diagrams in place and their links navigate.
- **App: light, dark and system themes** for the whole window, dialogs and menus included, and the theme is remembered.
- **App: analysis report.** What was read per language, the files that revealed each service, and diagnostics: files that could not be parsed, requests without an endpoint, endpoints nobody calls, flows that stop at the entry point.
- **App: export menu.** The zip, the diagram on screen as SVG or PNG, the diagram to the clipboard, or the page as Markdown.
- **App: recent projects** with what the last analysis found, a folder can be dropped anywhere on the window, and the window remembers its size.
- **App: cancel an analysis**, and problems explained in place: a folder that cannot be opened, a folder without code, a broken `xray.toml`.
- **Endpoints of FastAPI, Flask and NestJS**, so their projects get flows too. Calls are followed into Python modules imported from inside an app folder.
- **Packages as features** for projects organised by module, such as libraries and command-line tools.
- **Diagnostics** in `analysis.json` and in the command line's summary.
- Keyboard shortcuts for every main action, listed in the README.

### Changed

- **Diagrams: one visual language.** Every diagram has a marker of its level and the question it answers, groups cards in zones and shares its components with the other two.
- **Overview.** A zone per tier, with data stores told apart from external services. Services are ordered next to the apps that use them, connectors leave from ports and their labels sit in the gaps between zones. Connectors that skip a tier share one lane per service. Apps and services beyond the limit are named in a summary card instead of stretching the diagram.
- **Feature map.** A zone per app with its totals, and a connector between zones with the number of requests that cross. Chips stop after two rows with a "+N" chip; frontend cards count screens.
- **Flows.** The HTTP request is drawn where it crosses between apps, with its method in colour and its route; a flow no screen starts shows the request arriving. Steps show the type and the member called on it, and long titles wrap.
- **Progress is real.** The analysis screen shows each stage as pending, running or done and counts the files read; the bar of 1.0 followed invented fractions.
- **Edit texts** is one card per feature, grouped by app, with a filter, a view of what is in your words and a way back to what was found.
- **Faster on large projects.** Diagrams are drawn when first opened or exported, requests are linked through an index and parsed files are remembered. A synthetic project of 3,600 files with 2,400 endpoints is analysed in about 4 seconds; refreshing after editing a text takes under 2.
- Requests between a frontend and a backend are counted from the links found, and the overview and the feature map show the same number.
- Exports and saved texts answer with a toast instead of a message box.

### Fixed

- A `GET` flow said "stores the result"; the last card now says reads, stores or deletes according to the method, or "calls the service" when it is not a data store.
- The preview and the PNG copies were drawn in Qt's default font instead of the font a browser would use for the same SVG.
- Text outside ASCII was measured as wider than it is, so Spanish labels were cut early; long identifiers and routes are now broken where they read best or shortened in the middle.
- A folder without a build file (plain scripts) produced empty documents; it is analysed as one application.
- With several backends, every frontend was connected to every backend with the same total of requests.
- A file named `overview.py` was read as a screen called "Over".
- The theme switch only changed the diagram, leaving a dark diagram in a light window.

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

