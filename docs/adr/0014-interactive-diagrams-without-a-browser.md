# ADR-0014: Interactive diagrams without a browser

- Status: accepted
- Date: 2026-11-11

## Context

The redesign needed diagrams that zoom, pan, can be searched and whose cards lead to the pages they stand for, and pages that show their diagrams. The obvious tool is a web view: SVG with links and CSS, HTML pages. Qt's web view (QtWebEngine) is a browser engine of more than 100 MB; the executable is 37 MB and a single file by decision (ADR-0010). The diagrams must also stay plain SVG Tiny so that GitHub, browsers and Qt draw them the same way.

## Decision

Keep Qt's SVG renderer and build the interaction around the SVG text, which repo-xray writes itself and therefore knows:

- **Named cards.** Renderers give cards an `id` such as `feature-backend-resena` (`render/ids.py`). SVG ignores it when drawing. The canvas asks the renderer where each named element is and makes it react to the pointer; the app decides where a click leads. Only cards that lead somewhere other than the current document react.
- **A canvas widget** (`app/widgets/canvas.py`) that draws the SVG at any scale, so it stays sharp, with fit to width or to the whole diagram, zoom around the pointer and panning. Up to a size the drawing is kept as a pixmap; beyond it, it is drawn straight from the SVG.
- **Find** reads the diagram's `<text>` elements and measures them with the font Qt draws them in, to highlight matches.
- **Pages** are converted from repo-xray's own Markdown subset to rich text styled with the app's palette (`app/markdown_html.py`), with each embedded diagram drawn in place at the width of the text column. Qt's Markdown import cannot be styled.
- **Fonts.** Qt's SVG renderer does not walk a list of font families, so before drawing, each list is replaced by its first installed family. The exported SVG keeps the lists.

## Consequences

- The executable stays a single 37 MB file and the exported diagrams are unchanged in kind: static, portable SVG.
- The Markdown converter is not general: it covers what the generated pages and the report use, and a test converts real generated pages to catch what it misses.
- Hit areas are rectangles, the bounds of each named element. That is exact for cards.
- Hover effects, animated transitions and text selection inside a diagram are not available. A web view remains possible later if they become worth their weight.
