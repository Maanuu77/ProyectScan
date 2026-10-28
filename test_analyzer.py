from pathlib import Path
from textwrap import dedent

import pytest

from analyzer import analyze_file, analyze_project, analyze_source, module_name
from config import Config
from scanner import scan


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


def imports_as_tuples(info):
    return [(i.module, i.name, i.alias, i.level) for i in info.imports]


def test_absolute_imports():
    info = analyze("""
        import os
        import os.path as osp, json
        from collections import OrderedDict as OD, deque
    """)

    assert imports_as_tuples(info) == [
        ("os", None, None, 0),
        ("os.path", None, "osp", 0),
        ("json", None, None, 0),
        ("collections", "OrderedDict", "OD", 0),
        ("collections", "deque", None, 0),
    ]


@pytest.mark.parametrize(
    ("path", "code", "expected_module"),
    [
        ("pkg/sub/mod.py", "from . import x", "pkg.sub"),
        ("pkg/sub/mod.py", "from .utils import x", "pkg.sub.utils"),
        ("pkg/sub/mod.py", "from ..core import x", "pkg.core"),
        ("pkg/sub/__init__.py", "from .utils import x", "pkg.sub.utils"),
        ("pkg/sub/__init__.py", "from .. import x", "pkg"),
        ("mod.py", "from ...far import x", "...far"),
    ],
)
def test_relative_imports_are_resolved(path, code, expected_module):
    (imported,) = analyze(code, path).imports

    assert imported.module == expected_module
    assert imported.name == "x"


def test_import_scope_is_recorded():
    info = analyze("""
        import os

        def lazy():
            import json
    """)

    assert [(i.module, i.scope, i.lineno) for i in info.imports] == [
        ("os", "pkg.mod", 2),
        ("json", "pkg.mod.lazy", 5),
    ]


def calls_as_tuples(info):
    return [(c.caller, c.callee) for c in info.calls]


def test_calls_record_caller_and_dotted_callee():
    info = analyze("""
        setup()

        class Service:
            def run(self):
                self.repo.save(os.path.join("a", "b"))
                get_handler()()
    """)

    assert calls_as_tuples(info) == [
        ("pkg.mod", "setup"),
        ("pkg.mod.Service.run", "self.repo.save"),
        ("pkg.mod.Service.run", "os.path.join"),
        ("pkg.mod.Service.run", "get_handler"),
    ]


def test_decorators_and_defaults_belong_to_the_enclosing_scope():
    info = analyze("""
        class Api(make_base()):
            @route("/items")
            def items(self, limit=default_limit()):
                return query(limit)
    """)

    assert calls_as_tuples(info) == [
        ("pkg.mod", "make_base"),
        ("pkg.mod.Api", "route"),
        ("pkg.mod.Api", "default_limit"),
        ("pkg.mod.Api.items", "query"),
    ]


def test_calls_inside_lambdas_and_comprehensions_belong_to_the_function():
    info = analyze("""
        def build(items):
            key = lambda item: normalize(item)
            return [convert(i) for i in items]
    """)

    assert calls_as_tuples(info) == [
        ("pkg.mod.build", "normalize"),
        ("pkg.mod.build", "convert"),
    ]


def write(root: Path, relative: str, content: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return Path(relative)


def test_syntax_error_is_reported_not_raised(tmp_path):
    relative = write(tmp_path, "broken.py", b"def oops(:\n    pass\n")

    info = analyze_file(tmp_path, relative)

    assert info.name == "broken"
    assert info.error.startswith("SyntaxError")
    assert "line 1" in info.error
    assert info.symbols == []


def test_invalid_bytes_are_reported_not_raised(tmp_path):
    relative = write(tmp_path, "binary.py", b"x = 1\x00\xff\xfe\n")

    info = analyze_file(tmp_path, relative)

    assert info.error is not None


def test_encoding_declaration_is_respected(tmp_path):
    source = '# -*- coding: latin-1 -*-\ndef café():\n    """Olé."""\n'.encode("latin-1")
    relative = write(tmp_path, "legacy.py", source)

    info = analyze_file(tmp_path, relative)

    assert info.error is None
    assert info.symbols[0].docstring == "Olé."


def test_project_analysis_continues_after_a_broken_file(tmp_path):
    write(tmp_path, "a_broken.py", b"class :\n")
    write(tmp_path, "b_ok.py", b"def fine():\n    pass\n")

    modules = analyze_project(scan(tmp_path, Config()))

    assert [m.path for m in modules] == ["a_broken.py", "b_ok.py"]
    assert modules[0].error and not modules[1].error
    assert modules[1].symbols[0].name == "fine"
