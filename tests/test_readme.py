from textwrap import dedent

from repo_xray.analysis.readme import MAX_LENGTH, describe, first_paragraph


def test_skips_headings_html_badges_and_images():
    readme = dedent("""\
        <div align="center">

        # 🌳 Benchify

        **Mapa colaborativo de bancos públicos.** Descubre bancos cerca de ti
        y [valóralos](docs/x.md). Cada aportación pasa por `moderación`.

        [![CI](https://x/badge.svg)](https://x)
        ![Java 21](https://img.shields.io/badge/Java-21)

        </div>
    """)

    assert describe(readme) == ("Mapa colaborativo de bancos públicos. Descubre bancos cerca de ti "
                                "y valóralos. Cada aportación pasa por moderación.")


def test_blocks_mixing_prose_and_badges_are_decoration():
    readme = "# Tool\n\nBuild ![status](x.svg) passing\n![x](y.png)\n\nA small tool that tidies your downloads folder.\n"

    assert describe(readme) == "A small tool that tidies your downloads folder."


def test_long_paragraphs_keep_whole_sentences_up_to_the_limit():
    sentence = "This sentence is exactly long enough to be counted several times over. "
    text = describe(sentence * 10)

    assert len(text) <= MAX_LENGTH
    assert text.endswith(".")


def test_nothing_useful():
    assert describe("# Title\n\n| a | b |\n|---|---|\n\n```\ncode\n```\n") is None


def test_reads_the_readme_file(tmp_path):
    (tmp_path / "README.md").write_text("# X\n\nShows the weather for any city you type in.\n", encoding="utf-8")

    assert first_paragraph(tmp_path) == "Shows the weather for any city you type in."
    assert first_paragraph(tmp_path / "missing") is None
