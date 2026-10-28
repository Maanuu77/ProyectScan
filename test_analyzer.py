from pathlib import Path
from textwrap import dedent

import pytest

from analyzer import analyze_source, module_name


def analyze(code: str, path: str = "pkg/mod.py"):
    return analyze_source(dedent(code), Path(path))


def symbols_by_qualname(info):
    return {s.qualname: s for s in info.symbols}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("main.py", "main"),
        ("pkg/sub/mod.py", "pkg.sub.mod"),
        ("pkg/__init__.py", "pkg"),
        ("__init__.py", "__init__"),
    ],
)
def test_module_name(path, expected):
    assert module_name(Path(path)) == expected


def test_module_metadata():
    info = analyze('"""Module doc."""\nx = 1\n', "pkg/__init__.py")

    assert info.path == "pkg/__init__.py"
    assert info.name == "pkg"
    assert info.is_package
    assert info.line_count == 2
    assert info.docstring == "Module doc."


def test_functions_classes_and_methods():
    info = analyze('''
        def helper():
            """Help."""

        class Repo(Base, metaclass=Meta):
            def save(self):
                pass

            @staticmethod
            async def load():
                pass
    ''')

    symbols = symbols_by_qualname(info)
    assert set(symbols) == {"pkg.mod.helper", "pkg.mod.Repo", "pkg.mod.Repo.save", "pkg.mod.Repo.load"}

    assert symbols["pkg.mod.helper"].kind == "function"
    assert symbols["pkg.mod.helper"].docstring == "Help."
    assert symbols["pkg.mod.Repo"].kind == "class"
    assert symbols["pkg.mod.Repo"].bases == ["Base"]
    assert symbols["pkg.mod.Repo.save"].kind == "method"
    assert symbols["pkg.mod.Repo.save"].parent == "pkg.mod.Repo"

    load = symbols["pkg.mod.Repo.load"]
    assert load.is_async
    assert load.decorators == ["staticmethod"]


def test_line_ranges():
    info = analyze("""
        def first():
            a = 1
            return a
    """)

    (symbol,) = info.symbols
    assert (symbol.lineno, symbol.end_lineno) == (2, 4)


def test_nested_functions_and_classes():
    info = analyze("""
        def outer():
            def inner():
                pass

            class Local:
                def method(self):
                    pass
    """)

    symbols = symbols_by_qualname(info)
    assert symbols["pkg.mod.outer.inner"].kind == "function"
    assert symbols["pkg.mod.outer.inner"].parent == "pkg.mod.outer"
    assert symbols["pkg.mod.outer.Local.method"].kind == "method"
