"""Command-line entry point: python -m repo_xray <project> [--export docs.zip] [--json analysis.json]"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from repo_xray.config import load_config
from repo_xray.model import SourceFile
from repo_xray.pipeline import Analysis, analyse
from repo_xray.project import analysis_to_dict
from repo_xray.scanner import ScanResult


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="repo-xray",
        description="Analyse a project and generate its architecture documentation.",
    )
    parser.add_argument("project", type=Path, help="folder of the project to analyse")
    parser.add_argument("--export", type=Path, metavar="ZIP", help="write the documentation and diagrams to ZIP")
    parser.add_argument("--no-png", action="store_true", help="leave the PNG copies out of the zip")
    parser.add_argument("--json", type=Path, metavar="FILE", help="also write the parsed source files to FILE")
    return parser.parse_args(argv)


def summarize_analysis(analysis: Analysis) -> str:
    lines = [summarize(analysis.scan, analysis.files), ""]
    apps = ", ".join(f"{a.name} ({a.kind})" for a in analysis.stack.apps) or "none"
    services = ", ".join(s.name for s in analysis.stack.services) or "none"
    lines.append(f"  Apps      {apps}")
    lines.append(f"  Services  {services}")
    lines.append(f"  Features  {len(analysis.features.features)}")
    lines.append(f"  Flows     {len(analysis.flows)} ({len(analysis.links)} linked HTTP calls)")
    return "\n".join(lines)


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
        load_config(root)
    except ValueError as exc:  # includes tomllib.TOMLDecodeError
        print(f"error: invalid configuration: {exc}", file=sys.stderr)
        return 2

    analysis = analyse(root)
    print(summarize_analysis(analysis))

    if args.export:
        from repo_xray.export.archive import build_bundle, write_zip  # needs Qt for the PNG copies

        bundle = build_bundle(analysis, png=not args.no_png)
        write_zip(bundle, args.export)
        print(f"\nDocumentation written to {args.export} ({len(bundle)} files)")
    if args.json:
        data = analysis_to_dict(analysis.scan, analysis.files)
        args.json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nAnalysis written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
