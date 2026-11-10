"""The analysis report: what repo-xray read, why it believes what it shows, and what it could not resolve.

A page of the app, not of the exported documents: it is about the analysis,
for the person running it. It is written as Markdown so the page view
shows it like any other page.
"""

from collections import Counter

from repo_xray.analysis.diagnostics import ERROR, WARNING, Diagnostic
from repo_xray.pipeline import Analysis

TITLE = "Analysis report"
MAX_ITEMS = 40  # items listed under one note; the rest are counted
LANGUAGES = {"python": "Python", "java": "Java", "typescript": "TypeScript", "javascript": "JavaScript"}
KINDS = {"web": "Web app", "api": "API", "mobile": "Mobile app", "desktop": "Desktop app", "library": "Application"}
MARKS = {ERROR: "Problem", WARNING: "Warning"}


def build_report(analysis: Analysis) -> str:
    lines = [f"# {TITLE}", "", _headline(analysis), ""]
    lines += _notes(analysis.diagnostics)
    lines += _languages(analysis)
    lines += _apps(analysis)
    lines += _services(analysis)
    return "\n".join(lines)


def _headline(analysis: Analysis) -> str:
    files, lines = len(analysis.files), sum(f.line_count for f in analysis.files)
    took = f"{analysis.seconds:.1f} s" if analysis.seconds >= 0.1 else "under 0.1 s"
    return (f"**{analysis.stack.name}** · `{analysis.root}`\n\n"
            f"{_n(files, 'file')} and {_n(lines, 'line')} of code read in {took}: "
            f"{_n(len(analysis.stack.apps), 'application')}, {_n(len(analysis.stack.services), 'service')}, "
            f"{_n(len(analysis.features.features), 'feature')} and {_n(len(analysis.flows), 'flow')}.")


def _notes(diagnostics: list[Diagnostic]) -> list[str]:
    if not diagnostics:
        return ["## Notes", "", "Nothing to report: every file was read and every request found its endpoint.", ""]
    lines = ["## Notes", ""]
    for diagnostic in diagnostics:
        mark = MARKS.get(diagnostic.severity)
        lines += [f"### {mark + ': ' if mark else ''}{diagnostic.title}", "", diagnostic.detail, ""]
        lines += [f"- `{item}`" for item in diagnostic.items[:MAX_ITEMS]]
        if len(diagnostic.items) > MAX_ITEMS:
            lines.append(f"- … and {len(diagnostic.items) - MAX_ITEMS} more")
        if diagnostic.items:
            lines.append("")
    return lines


def _languages(analysis: Analysis) -> list[str]:
    files, code = Counter(), Counter()
    for file in analysis.files:
        files[file.language] += 1
        code[file.language] += file.line_count
    if not files:
        return []
    lines = ["## What was read", "", "| Language | Files | Lines |", "| --- | ---: | ---: |"]
    for language, count in files.most_common():
        lines.append(f"| {LANGUAGES.get(language, language)} | {count:,} | {code[language]:,} |")
    return [*lines, ""]


def _apps(analysis: Analysis) -> list[str]:
    if not analysis.stack.apps:
        return []
    lines = ["## Applications", "", "| Application | Kind | Folder | Built with | Files | Deployed to |",
             "| --- | --- | --- | --- | ---: | --- |"]
    for app in analysis.stack.apps:
        folder = "(project root)" if app.path == "." else f"`{app.path}`"
        lines.append(f"| {app.name} | {KINDS.get(app.kind, app.kind)} | {folder} | {', '.join(app.technologies) or '—'} "
                     f"| {app.files:,} | {', '.join(app.deployments) or '—'} |")
    return [*lines, ""]


def _services(analysis: Analysis) -> list[str]:
    if not analysis.stack.services:
        return []
    lines = ["## Services and the evidence for them", "",
             "Each service is on the overview because of something in the project. These are the files that revealed it.",
             "", "| Service | Used by | Found in |", "| --- | --- | --- |"]
    for service in analysis.stack.services:
        name = service.name + (f" ({', '.join(service.details)})" if service.details else "")
        evidence = ", ".join(f"`{path}`" for path in service.evidence[:4])
        if len(service.evidence) > 4:
            evidence += f" and {len(service.evidence) - 4} more"
        lines.append(f"| {name} | {', '.join(service.used_by) or '—'} | {evidence or '—'} |")
    return [*lines, ""]


def _n(count: int, noun: str) -> str:
    return f"{count:,} {noun}" if count == 1 else f"{count:,} {noun}s"
