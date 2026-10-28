# ADR-0010: A single-file Windows executable built with PyInstaller

- Status: accepted
- Date: 2026-10-28

## Context

ADR-0006 promises an app that beginners can run without installing Python. Options to package it:

- PyInstaller, one folder: starts fastest, but users get a folder with hundreds of files and must find the right one.
- PyInstaller, one file: a single `repo-xray.exe`; it unpacks itself at start-up, which costs a second or two.
- Nuitka: compiles to C and starts faster, but needs a C compiler on the build machine and builds take much longer.
- An installer (MSI, Inno Setup): the most familiar experience, but one more tool to maintain and a signed installer to trust.

## Decision

Ship a single windowed executable built with PyInstaller (`packaging/build.py`):

- `--onefile` and `--windowed`: download, double-click, no console window.
- The icon is generated during the build from `repo_xray/app/icon.svg` as a multi-size `.ico`, so no binary file is edited by hand.
- Qt modules the app does not use (QML, Quick, network, PDF, SQL…) are excluded.
- With arguments, the same executable still runs the command line, which lets CI smoke-test the packaged app.

## Consequences

- Measured on Windows 11: a 36 MB file whose window opens in about 1.5 s.
- The executable is not code-signed, so Windows SmartScreen may warn on first launch; the README explains how to continue. Signing would need a paid certificate.
- macOS and Linux builds can reuse the same script later.
