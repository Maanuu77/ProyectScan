"""Language-neutral description of a source file.

Every parser (Python, Java, TypeScript) fills these dataclasses, so
everything after parsing works the same for every language.
"""

from dataclasses import dataclass, field


@dataclass
class Symbol:
    kind: str  # "class", "interface", "enum", "record", "function" or "method"
    name: str
    qualname: str  # dotted, starting with the file's module name
    parent: str  # qualname of the enclosing module, type or function
    lineno: int
    end_lineno: int
    docstring: str | None  # docstring, Javadoc or JSDoc
    decorators: list[str] = field(default_factory=list)  # decorators or annotations, as written
    bases: list[str] = field(default_factory=list)  # superclasses and implemented interfaces
    is_async: bool = False


@dataclass
class Import:
    module: str  # absolute module, package or project-relative path
    name: str | None  # the imported name in `from module import name`
    alias: str | None
    level: int  # leading dots of a Python relative import, 0 otherwise
    lineno: int
    scope: str  # qualname of the scope where the import happens


@dataclass
class Call:
    caller: str  # qualname of the scope that makes the call
    callee: str  # the called expression as written, e.g. `self.repo.save`
    lineno: int


@dataclass
class Endpoint:
    """An HTTP route served by this file, e.g. a Spring `@GetMapping`."""

    method: str  # GET, POST, PUT, PATCH, DELETE or ANY
    path: str  # route with parameters as `{name}`, e.g. /api/v1/bancos/{id}
    handler: str  # qualname of the function that handles it
    lineno: int
    summary: str | None = None


@dataclass
class HttpCall:
    """An HTTP request made from this file, e.g. `this.http.get(...)`."""

    method: str
    url: str  # template with interpolations as `{expr}`, e.g. {this.url}/bancos/{id}
    caller: str
    lineno: int


@dataclass
class SourceFile:
    path: str  # relative to the project root, with forward slashes
    language: str  # "python", "java" or "typescript"
    name: str  # module name: dotted for Python and Java, path without extension for TypeScript
    package: str  # enclosing package or folder
    line_count: int
    is_package: bool = False  # Python `__init__.py`
    docstring: str | None = None
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    http_calls: list[HttpCall] = field(default_factory=list)
    error: str | None = None  # set when the file could not be parsed
