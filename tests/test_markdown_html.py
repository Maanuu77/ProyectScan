import re

from repo_xray.app.markdown_html import diagram_name, to_html
from repo_xray.app.report import build_report
from repo_xray.app.theme import DARK, LIGHT, PALETTES
from repo_xray.export.markdown import FOLDER, build_documents, feature_page
from repo_xray.pipeline import analyse
from tests.conftest import hexagonal_backend, write

LIGHT_PALETTE = PALETTES[LIGHT]


def html(markdown: str) -> str:
    return to_html(markdown, LIGHT_PALETTE)


def plain(markup: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup).replace("&nbsp;", " ")).strip()


def test_headings_paragraphs_and_inline_styles():
    result = html("# Title\n\nSome **bold**, _quiet_ and `code` text\nover two lines.\n\n## Section\n")

    assert "<h1" in result and "<h2" in result
    assert plain(result) == "Title Some bold , quiet and code text over two lines. Section"
    assert "font-weight: 600" in result and "font-style: italic" in result and "Consolas" in result


def test_lists_and_rules():
    result = html("- one\n- [two](features/two.md)\n\n---\n\nafter\n")

    assert result.count("<li") == 2 and "<hr" in result
    assert '<a href="features/two.md"' in result


def test_tables_align_numbers_and_keep_escaped_bars():
    result = html("| Layer | Files |\n| --- | ---: |\n| Entry points | 3 |\n| a \\| b | 12 |\n")

    assert result.count("<tr>") == 3 and result.count("<th") == 2 and result.count("<td") == 4
    assert 'align="right"' in result and 'align="left"' in result
    assert "a | b" in plain(result)
    assert "border-collapse: collapse" in result


def test_a_quote_gets_an_accent_bar():
    result = html("> A small shop\n> for good things\n")

    assert LIGHT_PALETTE.accent in result
    assert plain(result) == "A small shop for good things"


def test_a_picture_becomes_a_diagram_that_opens_when_clicked():
    result = html('<picture>\n  <source media="(prefers-color-scheme: dark)" srcset="../images/flow-post-api-orders-dark.svg">\n'
                  '  <img alt="Place an order" src="../images/flow-post-api-orders-light.svg">\n</picture>\n')

    assert '<a href="diagram:flow-post-api-orders"><img src="diagram:flow-post-api-orders" alt="Place an order" /></a>' in result
    assert diagram_name("diagram:flow-post-api-orders") == "flow-post-api-orders"
    assert diagram_name("features/x.md") is None and diagram_name("https://example.com") is None


def test_details_show_their_summary_and_content():
    result = html("<details><summary>2 files</summary>\n\n- `a.py`\n- `b.py`\n\n</details>\n")

    assert plain(result) == "2 files a.py b.py"
    assert "<details" not in result and "<summary" not in result


def test_text_from_the_project_cannot_inject_markup():
    result = html("A <script>alert(1)</script> & `<b>` in a [link](x.md)\n")

    assert "<script>" not in result and "&lt;script&gt;" in result
    assert "&lt;b&gt;" in result and "&amp;" in result


def test_colours_follow_the_palette():
    dark = to_html("> quote\n\n[link](x.md)\n", PALETTES[DARK])

    assert PALETTES[DARK].accent in dark and PALETTES[DARK].accent_text in dark
    assert LIGHT_PALETTE.accent_text not in dark


def test_generated_pages_convert_without_leftovers(tmp_path):
    hexagonal_backend(tmp_path)
    analysis = analyse(tmp_path)
    bundle = build_documents(analysis)

    for path in (f"{FOLDER}/README.md", feature_page("api/order")):
        result = html(str(bundle[path]))
        text = plain(result)
        assert "<picture" not in result and "<details" not in result
        assert "**" not in text and "](" not in text and "|" not in text.replace("a | b", "")
    index = html(str(bundle[f"{FOLDER}/README.md"]))
    assert 'src="diagram:overview"' in index and 'src="diagram:features"' in index
    assert '<a href="features/api-order.md"' in index


def test_report_says_what_was_read_and_why(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, {
        "api/tools/bad.py": "def broken(:\n",
        "compose.yaml": "services:\n  db:\n    image: postgres:17\n",
    })

    report = build_report(analyse(tmp_path))

    assert report.startswith("# Analysis report")
    assert "### Warning: 1 file could not be read" in report and "- `api/tools/bad.py: SyntaxError" in report
    assert "| Java |" in report and "| Python | 1 |" in report
    assert "| api | API | `api` | Spring Boot" in report
    assert "| PostgreSQL | api | `compose.yaml` |" in report  # the evidence behind the service
    text = plain(html(report))
    assert "Services and the evidence for them" in text and "compose.yaml" in text


def test_report_of_a_clean_project_says_so(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "tool"\ndescription = "A tool."\n',
                     "tool.py": '"""Does things."""\nx = 1\n'})
    analysis = analyse(tmp_path)
    analysis.diagnostics.clear()

    assert "Nothing to report" in build_report(analysis)
