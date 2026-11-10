"""Turn the Markdown that repo-xray writes into HTML for the app's page view.

Not a general Markdown converter: it covers what the generated pages and
the analysis report use (headings, paragraphs, lists, tables, quotes,
rules, bold, italics, code, links, images, `<picture>` and `<details>`),
and styles it with the app's palette. Qt's own Markdown import cannot be
styled and draws tables with its default borders.
"""

import html
import re

from repo_xray.app.theme import Palette

DIAGRAM_SCHEME = "diagram"  # `diagram:overview` stands for a diagram of the bundle, drawn by the page view

_PICTURE = re.compile(r'<picture>.*?srcset="[^"]*?([^/"]+)-dark\.svg".*?alt="([^"]*)".*?</picture>', re.S)
_DETAILS = re.compile(r"<details>\s*<summary>(.*?)</summary>(.*?)</details>", re.S)
_INLINE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<linked>\[!\[(?P<lalt>[^\]]*)\]\((?P<lsrc>[^)\s]+)\)\]\((?P<lhref>[^)\s]+)\))"
    r"|(?P<image>!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\))"
    r"|(?P<link>\[(?P<text>[^\]]+)\]\((?P<href>[^)\s]+)\))"
    r"|(?P<bold>\*\*(?P<strong>.+?)\*\*)"
    r"|(?P<italic>(?<![\w*])[*_](?P<em>[^*_\s][^*_]*?)[*_](?![\w*]))"
)
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def to_html(markdown: str, palette: Palette, mono: str = "Consolas") -> str:
    """The page as an HTML fragment styled with `palette`."""
    return _Converter(palette, mono).convert(markdown)


def diagram_name(url: str) -> str | None:
    """`diagram:overview` -> `overview`; None for any other address."""
    scheme, _, name = url.partition(":")
    return name if scheme == DIAGRAM_SCHEME and name else None


class _Converter:
    def __init__(self, palette: Palette, mono: str):
        self.p = palette
        self.mono = mono

    def convert(self, markdown: str) -> str:
        text = _PICTURE.sub(lambda m: f"[![{m.group(2)}]({DIAGRAM_SCHEME}:{m.group(1)})]({DIAGRAM_SCHEME}:{m.group(1)})",
                            markdown)
        text = _DETAILS.sub(lambda m: f"\n\n**{m.group(1).strip()}**\n\n{m.group(2).strip()}\n\n", text)
        blocks = [self._block(block) for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
        return "".join(blocks)

    # Blocks

    def _block(self, block: str) -> str:
        p = self.p
        lines = [line.rstrip() for line in block.strip().splitlines()]
        first = lines[0].lstrip()
        heading = re.match(r"(#{1,4})\s+(.*)", first)
        if heading and len(lines) == 1:
            return self._heading(len(heading.group(1)), heading.group(2))
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", first) and len(lines) == 1:
            return f'<hr style="background-color: {p.border};" />'
        if len(lines) >= 2 and "|" in lines[0] and _TABLE_RULE.match(lines[1]):
            return self._table(lines)
        if all(line.lstrip().startswith(("- ", "* ")) for line in lines):
            items = "".join(f'<li style="margin-bottom: 4px;">{self._inline(line.lstrip()[2:])}</li>' for line in lines)
            return f'<ul style="margin-top: 4px; margin-bottom: 12px; margin-left: 4px;">{items}</ul>'
        if all(line.lstrip().startswith(">") for line in lines):
            quote = " ".join(line.lstrip()[1:].strip() for line in lines)
            return (f'<table cellspacing="0" cellpadding="0" style="margin-top: 4px; margin-bottom: 14px;"><tr>'
                    f'<td width="3" style="background-color: {p.accent};"></td>'
                    f'<td style="padding: 6px 0px 6px 14px; color: {p.text}; font-size: 15px;">{self._inline(quote)}</td>'
                    f"</tr></table>")
        if len(lines) == 1 and re.fullmatch(r"\[!\[[^\]]*\]\([^)]+\)\]\([^)]+\)|!\[[^\]]*\]\([^)]+\)", first):
            return f'<p style="margin-top: 6px; margin-bottom: 18px;">{self._inline(first)}</p>'
        return f'<p style="margin-top: 0px; margin-bottom: 12px;">{self._inline(" ".join(line.strip() for line in lines))}</p>'

    def _heading(self, level: int, text: str) -> str:
        sizes = {1: (26, 4, 14), 2: (19, 26, 10), 3: (15, 20, 8), 4: (13, 16, 6)}
        size, top, bottom = sizes[level]
        return (f'<h{level} style="font-size: {size}px; font-weight: 700; color: {self.p.text}; '
                f'margin-top: {top}px; margin-bottom: {bottom}px;">{self._inline(text)}</h{level}>')

    def _table(self, lines: list[str]) -> str:
        p = self.p
        header = _cells(lines[0])
        alignments = ["right" if cell.strip().endswith(":") else "left" for cell in _cells(lines[1])]
        alignments += ["left"] * (len(header) - len(alignments))
        border = f"border: 1px solid {p.border};"
        rows = ['<tr>' + "".join(
            f'<th align="{alignments[i]}" style="{border} background-color: {p.sidebar}; color: {p.text_muted}; '
            f'font-size: 12px; font-weight: 600; padding: 4px 12px;">{self._inline(cell)}</th>'
            for i, cell in enumerate(header)) + "</tr>"]
        for line in lines[2:]:
            cells = _cells(line)
            cells += [""] * (len(header) - len(cells))
            rows.append("<tr>" + "".join(
                f'<td align="{alignments[i]}" style="{border} padding: 4px 12px;">{self._inline(cell)}</td>'
                for i, cell in enumerate(cells[:len(header)])) + "</tr>")
        return (f'<table cellspacing="0" cellpadding="0" style="border-collapse: collapse; {border} '
                f'margin-top: 4px; margin-bottom: 16px;">{"".join(rows)}</table>')

    # Inline

    def _inline(self, text: str) -> str:
        p = self.p
        out, position = [], 0
        for match in _INLINE.finditer(text):
            out.append(html.escape(text[position:match.start()], quote=False))
            position = match.end()
            if match.group("code"):
                code = html.escape(match.group("code")[1:-1], quote=False)
                out.append(f'<span style="font-family: \'{self.mono}\'; font-size: 12px; color: {p.text}; '
                           f'background-color: {p.hover};">&nbsp;{code}&nbsp;</span>')
            elif match.group("linked"):  # an image that is also a link: a diagram that opens when clicked
                out.append(f'<a href="{html.escape(match.group("lhref"))}"><img src="{html.escape(match.group("lsrc"))}" '
                           f'alt="{html.escape(match.group("lalt"))}" /></a>')
            elif match.group("image"):
                out.append(f'<img src="{html.escape(match.group("src"))}" alt="{html.escape(match.group("alt"))}" />')
            elif match.group("link"):
                inner = self._inline(match.group("text"))
                out.append(f'<a href="{html.escape(match.group("href"))}" style="color: {p.accent_text}; '
                           f'text-decoration: none;">{inner}</a>')
            elif match.group("bold"):
                out.append(f'<span style="font-weight: 600;">{self._inline(match.group("strong"))}</span>')
            else:
                out.append(f'<span style="font-style: italic; color: {p.text_muted};">{self._inline(match.group("em"))}</span>')
        out.append(html.escape(text[position:], quote=False))
        return "".join(out)


def _cells(line: str) -> list[str]:
    """Cells of a table row; `\\|` inside a cell is a literal bar."""
    line = line.strip()
    line = line[1:] if line.startswith("|") else line
    line = line[:-1] if line.endswith("|") and not line.endswith("\\|") else line
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", line)]
