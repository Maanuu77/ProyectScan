"""Run every analysis step on a project, reporting progress along the way.

The CLI and the desktop app both call `analyse()`, so they always produce
the same result. Progress is reported as facts (which stage is running,
how many files of how many have been read), never as an invented
percentage, and the caller may cancel between any two files or stages.
"""

import re
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from repo_xray import i18n
from repo_xray.analysis.calls import CallGraph, build_call_graph
from repo_xray.analysis.diagnostics import Diagnostic, diagnose
from repo_xray.analysis.features import FeatureMap, detect_features
from repo_xray.analysis.flows import Flow, build_flows, pick_flows
from repo_xray.analysis.linking import HttpLink, link_http_calls
from repo_xray.analysis.stack import Stack, detect_stack
from repo_xray.analysis.texts import apply_user_texts, describe_features
from repo_xray.config import Config, load_config
from repo_xray.model import SourceFile
from repo_xray.parsers import language_of, parse_source, read_source
from repo_xray.parsers.cache import ParseCache
from repo_xray.scanner import ScanResult, scan

# Stages in the order they run, with the words shown to the user while each one runs.
STAGES: dict[str, str] = {
    "scan": "Looking for source files",
    "parse": "Reading the code",
    "stack": "Detecting apps and services",
    "calls": "Following calls between files",
    "features": "Grouping code into features",
    "flows": "Tracing request flows",
    "texts": "Writing names and descriptions",
}
REPORT_EVERY = 10  # files between two progress reports while parsing
READ_THREADS = 8  # reading waits on the disk and on antivirus scans, which threads can overlap
READ_AHEAD = 64  # files read ahead of the parser, so memory stays bounded on huge projects


@dataclass(frozen=True)
class Progress:
    """Where the analysis is: a stage and, when the stage can be counted, how far it got."""

    stage: str  # a key of STAGES; callers may add their own stages after these
    done: int = 0
    total: int = 0  # 0: the stage has nothing to count, only "running"
    detail: str = ""  # e.g. the file being read

    @property
    def label(self) -> str:
        return STAGES.get(self.stage, self.stage)


ProgressCallback = Callable[[Progress], None]


class Cancelled(Exception):
    """Raised inside `analyse()` when the caller asked to stop."""


@dataclass
class Analysis:
    root: Path
    scan: ScanResult
    files: list[SourceFile]
    stack: Stack
    graph: CallGraph
    links: list[HttpLink]
    features: FeatureMap
    flows: list[Flow] = field(default_factory=list)  # every flow, one per endpoint
    highlights: list[Flow] = field(default_factory=list)  # the few shown on the main page
    language: str = i18n.DEFAULT  # language of the documents: "en" or "es"
    detected_language: str = i18n.DEFAULT  # what the code suggests, before the user's choice
    config: Config = field(default_factory=Config)
    seconds: float = 0.0  # how long the analysis took
    diagnostics: list[Diagnostic] = field(default_factory=list)  # what could not be read, linked or resolved


def analyse(root: Path, progress: ProgressCallback | None = None,
            cancelled: Callable[[], bool] | None = None, cache: ParseCache | None = None) -> Analysis:
    """Analyse the project at `root`.

    `progress` receives a `Progress` at the start of every stage and every few
    files while parsing. `cancelled` is polled at the same points; when it
    returns True the analysis stops by raising `Cancelled`. With a `cache`,
    files that have not changed since an earlier analysis are not read again.
    """
    started = time.perf_counter()

    def report(stage: str, done: int = 0, total: int = 0, detail: str = "") -> None:
        if cancelled is not None and cancelled():
            raise Cancelled()
        if progress is not None:
            progress(Progress(stage, done, total, detail))

    report("scan")
    config = load_config(root)
    scan_result = scan(root, config)

    sources = [p for p in scan_result.files if language_of(p)]
    files = _parse(scan_result.root, sources, report, cache)

    report("stack")
    stack = detect_stack(scan_result, files)
    report("calls")
    graph = build_call_graph(files)
    links = link_http_calls(files)
    report("features")
    features = detect_features(stack, files, graph, links)
    report("flows")
    flows = build_flows(stack, files, graph, links, features)
    report("texts")
    detected = i18n.detect_language([stack.description, *_prose(files)])
    language = config.language or detected
    describe_features(features, files, stack, language)
    apply_user_texts(features, stack, config)
    diagnostics = diagnose(scan_result, files, stack, links, features, flows)
    return Analysis(scan_result.root, scan_result, files, stack, graph, links, features, flows, pick_flows(flows),
                    language, detected, config, seconds=time.perf_counter() - started, diagnostics=diagnostics)


def _parse(root: Path, sources: list[Path], report, cache: ParseCache | None) -> list[SourceFile]:
    """Parse `sources` in order. Files are read a few at a time on threads, then parsed here one by one."""
    files: list[SourceFile] = []
    total = len(sources)
    pool = ThreadPoolExecutor(max_workers=READ_THREADS, thread_name_prefix="repo-xray-read")
    try:
        for start in range(0, total, READ_AHEAD):
            batch = sources[start:start + READ_AHEAD]
            stamps = [ParseCache.stamp(root, path) if cache is not None else None for path in batch]
            known = [cache.lookup(root, path, stamp) if cache is not None else None
                     for path, stamp in zip(batch, stamps)]
            reads = [None if file is not None else pool.submit(read_source, root, path)
                     for path, file in zip(batch, known)]
            for offset, (path, stamp, file, read) in enumerate(zip(batch, stamps, known, reads)):
                if (start + offset) % REPORT_EVERY == 0:
                    report("parse", start + offset, total, path.as_posix())
                if file is None:
                    file = parse_source(read.result(), path)
                    if cache is not None:
                        cache.store(root, path, stamp, file)
                files.append(file)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)  # a cancelled analysis does not wait for the disk
    report("parse", total, total)
    return files


_QUOTED = re.compile(r'"([^"]{3,})"')


def _prose(files: list[SourceFile]) -> Iterator[str | None]:
    """Text written by people: docstrings, endpoint summaries and strings inside annotations."""
    for file in files:
        yield file.docstring
        for symbol in file.symbols:
            yield symbol.docstring
            for decorator in symbol.decorators:
                yield from _QUOTED.findall(decorator)
        for endpoint in file.endpoints:
            yield endpoint.summary
