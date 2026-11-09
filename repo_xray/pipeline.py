"""Run every analysis step on a project, reporting progress along the way.

The CLI and the desktop app both call `analyse()`, so they always produce
the same result. Progress is reported as facts (which stage is running,
how many files of how many have been read), never as an invented
percentage, and the caller may cancel between any two files or stages.
"""

import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from repo_xray import i18n
from repo_xray.analysis.calls import CallGraph, build_call_graph
from repo_xray.analysis.features import FeatureMap, detect_features
from repo_xray.analysis.flows import Flow, build_flows, pick_flows
from repo_xray.analysis.linking import HttpLink, link_http_calls
from repo_xray.analysis.stack import Stack, detect_stack
from repo_xray.analysis.texts import apply_user_texts, describe_features
from repo_xray.config import Config, load_config
from repo_xray.model import SourceFile
from repo_xray.parsers import language_of, parse_file
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


def analyse(root: Path, progress: ProgressCallback | None = None,
            cancelled: Callable[[], bool] | None = None) -> Analysis:
    """Analyse the project at `root`.

    `progress` receives a `Progress` at the start of every stage and every few
    files while parsing. `cancelled` is polled at the same points; when it
    returns True the analysis stops by raising `Cancelled`.
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
    files = []
    for index, path in enumerate(sources):
        if index % REPORT_EVERY == 0:
            report("parse", index, len(sources), path.as_posix())
        files.append(parse_file(scan_result.root, path))
    report("parse", len(sources), len(sources))

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
    return Analysis(scan_result.root, scan_result, files, stack, graph, links, features, flows, pick_flows(flows),
                    language, detected, config, seconds=time.perf_counter() - started)


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
