"""Command-line entry point: python -m repo_xray <project> [--json analysis.json]"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from repo_xray.model import SourceFile
from repo_xray.project import analysis_to_dict, analyze_project
from repo_xray.config import load_config
from repo_xray.scanner import ScanResult, scan


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="repo-xray",
        description="Analyse a Python project and summarise its structure.",
    )
    parser.add_argument("project", type=Path, help="folder of the project to analyse")
    parser.add_argument("--json", type=Path, metavar="FILE", help="also write the full analysis to FILE")
    return parser.parse_args(argv)


def summarize(scan_result: ScanResult, files: list[SourceFile]) -> str:
    kinds = Counter(symbol.kind for file in files for symbol in file.symbols)
    broken = [file for file in files if file.error]
    rows = [
        ("Files", len(files)),
        ("Lines", sum(file.line_count for file in files)),
        ("Classes", kinds["class"]),
        ("Functions", kinds["function"]),
        ("Methods", kinds["method"]),
        ("Imports", sum(len(file.imports) for file in files)),
        ("Calls", sum(len(file.calls) for file in files)),
    ]

    lines = [f"repo-xray - {scan_result.root}", ""]
    lines += [f"  {label:<10}{value:>8}" for label, value in rows]

    if broken:
        lines += ["", f"Could not parse {len(broken)} file(s):"]
        lines += [f"  {file.path}: {file.error}" for file in broken]
    if scan_result.skipped_large:
        lines += ["", f"Skipped {len(scan_result.skipped_large)} file(s) over the size limit:"]
        lines += [f"  {path.as_posix()}" for path in scan_result.skipped_large]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root: Path = args.project
    if not root.is_dir():
        print(f"error: {root} is not a folder", file=sys.stderr)
        return 2
    try:
        config = load_config(root)
    except ValueError as exc:  # includes tomllib.TOMLDecodeError
        print(f"error: invalid configuration: {exc}", file=sys.stderr)
        return 2

    scan_result = scan(root, config)
    files = analyze_project(scan_result)
    print(summarize(scan_result, files))

    if args.json:
        data = analysis_to_dict(scan_result, files)
        args.json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nAnalysis written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
