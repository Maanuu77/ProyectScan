"""Parse every file of a scanned project and export the result as JSON-ready data."""

from dataclasses import asdict

from repo_xray.model import SourceFile
from repo_xray.parsers import language_of, parse_file
from repo_xray.scanner import ScanResult

SCHEMA_VERSION = 2


def analyze_project(scan_result: ScanResult) -> list[SourceFile]:
    return [parse_file(scan_result.root, path) for path in scan_result.files if language_of(path)]


def analysis_to_dict(scan_result: ScanResult, files: list[SourceFile]) -> dict:
    """JSON-ready form of an analysis, so analysing and displaying can be debugged apart."""
    return {
        "schema_version": SCHEMA_VERSION,
        "root": scan_result.root.as_posix(),
        "skipped_large": [p.as_posix() for p in scan_result.skipped_large],
        "files": [asdict(file) for file in files],
    }
