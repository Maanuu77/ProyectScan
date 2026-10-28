# ADR-0006: Desktop app as the main interface

- Status: accepted
- Date: 2026-10-28

## Context

The tool must be usable by beginner programmers who are not comfortable with a terminal, Python installations or virtual environments.

Options considered:

- CLI only: simplest, but excludes the target users.
- Web app: no installation, but the analysed code would have to be uploaded, and free hosting cannot run a local LLM.
- Desktop app packaged as an executable: the code never leaves the computer and nothing has to be installed.

## Decision

Build a desktop app with PySide6 (Qt) and ship it as a Windows executable built with PyInstaller. The user chooses a folder, sees a preview and exports the zip. The CLI stays as a thin wrapper over the same engine for testing and automation.

Qt also renders SVG natively (`QtSvg`), so the same library previews the diagrams and converts them to PNG without extra native dependencies such as Cairo.

## Consequences

- The engine must not depend on the GUI: analysis runs in a background thread and reports progress through callbacks.
- Only `PySide6-Essentials` is used, to keep the executable small.
- Windows is the first target; macOS and Linux builds are left for after 1.0.0.
