"""What a project says about itself: the first real paragraph of its README."""

import re
from pathlib import Path

README_NAMES = ("README.md", "readme.md", "Readme.md", "README.MD", "README.rst", "README.txt", "README")
MAX_LENGTH = 320

# Lines that are not prose: headings, HTML, images, badges, tables, code fences, rules, quotes of admonitions.
_NOT_PROSE = re.compile(r"^\s*(#|<|!\[|\[!\[|\||```|~~~|---|\*\*\*|===|>\s*\[!)")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_FORMATTING = re.compile(r"(\*\*|__|`|(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w))")
_TAG = re.compile(r"<[^>]+>")


def first_paragraph(root: Path) -> str | None:
    for name in README_NAMES:
        path = root / name
        if path.is_file():
            try:
                return describe(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                return None
    return None


def describe(markdown: str) -> str | None:
    """The first paragraph of prose, without Markdown formatting, at most two sentences."""
    for block in re.split(r"\n\s*\n", markdown):
        lines = [line.strip() for line in block.strip().splitlines()]
        prose = [line for line in lines if line and not _NOT_PROSE.match(line)]
        if not prose or len(prose) < len([line for line in lines if line]):
            continue  # a block mixing prose with badges or HTML is decoration, not a description
        text = " ".join(prose)
        text = _LINK.sub(r"\1", text)
        text = _TAG.sub("", text)
        text = _FORMATTING.sub("", text)
        text = " ".join(text.split())
        if len(text) < 20 or not re.search(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]{3}", text):
            continue
        return _shorten(text)
    return None


def _shorten(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = sentences[0]
    for sentence in sentences[1:]:
        if len(result) + 1 + len(sentence) > MAX_LENGTH:
            break
        result += " " + sentence
    if len(result) > MAX_LENGTH:
        result = result[:MAX_LENGTH].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return result
