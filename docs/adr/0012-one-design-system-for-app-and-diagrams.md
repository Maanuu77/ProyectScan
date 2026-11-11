# ADR-0012: One design system for the app, built around the diagrams

- Status: accepted
- Date: 2026-11-11

## Context

In 1.0 the app had one style sheet that followed the system's light or dark mode at start, and a Light/Dark switch that only changed the diagram. A dark diagram sat in a light window, dialogs and menus kept the platform's look, and every screen chose its own spacing and colours. The diagrams, on the other hand, already had a palette: GitHub's, so that they look native in a README in either theme.

## Decision

The app gets one source for its look, `app/theme.py`:

- A `Palette` per mode with named roles (canvas, sidebar, surface, hover, border, text, accent, success, warning, danger). The style sheet is a template whose `@tokens` are replaced by the palette, and widgets that paint by hand read the same palette.
- The canvas colour of each palette **is** the background of the diagrams' theme. A diagram sits in the window without a visible edge, and the diagrams keep GitHub's palette because that is where they are read.
- `Themes` owns the mode: follow the system, light or dark. It is remembered, restyles the whole application at once and tells hand-painted widgets to repaint. Changing it redraws the document on show in the matching theme.
- One accent colour means "act here": the primary button, the selected row, focus. Everything else is neutral.
- Icons are a single family drawn on a 24-unit grid (`app/icons.py`) and stroked in a palette colour, so they follow the theme and every state of a control.
- Tests check text contrast (WCAG AA) on every surface of both palettes, and that the style sheet uses only colours the palette has.

## Consequences

- A new screen cannot drift: it has no colours of its own to choose.
- Light and dark are complete by construction. A third theme is a third `Palette`.
- The app's chrome is tied to the diagrams' backgrounds. If the diagrams' palette changes, the app follows.
- Qt style sheets cannot express everything (letter spacing, the gap between an icon and its text), so a few details are set in code next to the widget.
