"""Run every analysis step on a project, reporting progress along the way.

The CLI and the desktop app both call `analyse()`, so they always produce
the same result.
"""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from repo_xray import i18n
from repo_xray.analysis.calls import CallGraph, build_call_graph
from repo_xray.analysis.features import FeatureMap, detect_features
from repo_xray.analysis.flows import Flow, build_flows, pick_flows
from repo_xray.analysis.linking import HttpLink, link_http_calls
from repo_xray.analysis.stack import Stack, detect_stack
from repo_xray.config import load_config
from repo_xray.model import SourceFile
from repo_xray.parsers import language_of, parse_file
from repo_xray.scanner import ScanResult, scan

Progress = Callable[[str, float], None]  # (message, fraction done from 0 to 1)


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


def analyse(root: Path, progress: Progress | None = None) -> Analysis:
    report = progress or (lambda message, fraction: None)

    report("Looking for source files", 0.0)
    scan_result = scan(root, load_config(root))

    sources = [p for p in scan_result.files if language_of(p)]
    files = []
    for index, path in enumerate(sources):
        if index % 25 == 0:
            report(f"Reading {path.as_posix()}", 0.05 + 0.6 * index / max(len(sources), 1))
        files.append(parse_file(scan_result.root, path))

    report("Detecting apps and services", 0.7)
    stack = detect_stack(scan_result, files)
    report("Following calls between files", 0.78)
    graph = build_call_graph(files)
    links = link_http_calls(files)
    report("Grouping code into features", 0.86)
    features = detect_features(stack, files, graph, links)
    report("Tracing request flows", 0.93)
    flows = build_flows(stack, files, graph, links, features)
    report("Done", 1.0)
    language = i18n.detect_language([stack.description, *_prose(files)])
    return Analysis(scan_result.root, scan_result, files, stack, graph, links, features, flows, pick_flows(flows),
                    language)


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
