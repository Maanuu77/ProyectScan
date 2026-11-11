# ADR-0015: Documents written when they are first read

- Status: accepted
- Date: 2026-11-11

## Context

The documentation set was a dictionary built in one go: every page and every diagram, in both themes. A project with 300 features has about 900 flow diagrams, twice. Measured on a synthetic project of 909 files, drawing them took several seconds (12.8 s under the profiler) before the first diagram could be shown, although the app shows one diagram at a time and most are never opened.

## Decision

`Bundle` reads like a dictionary, but a document can be added as a function that writes it (`bundle.later(path, write)`). It is written the first time it is read and kept.

- Diagrams and `analysis.json` are added this way; pages are cheap and written at once.
- The app draws the overview and the feature map with the analysis, because it opens on them, and every other diagram when it is opened, in the theme on show.
- An export reads everything, so it draws everything, on the background task that writes the zip.
- Asking whether a path is in the bundle does not write it.

Two more changes came from the same measurements: HTTP requests are linked through an index of endpoints by method and last segment instead of comparing each request with every endpoint, and parsed files are remembered by path, size and modification time, so a refresh after editing a text reads only what changed.

## Consequences

- Building the documents for the 909-file project takes 0.08 s; on 3,600 files the whole analysis is a few seconds, and what it costs grows with the project, not with its square.
- A mistake in a diagram shows up when that diagram is opened, not when the project is analysed. A test opens every document of an odd project in the app, and another checks that an export leaves nothing unwritten.
- Code that iterates over the whole bundle pays for all of it. That is what an export wants; anything else should ask for the paths it needs.
