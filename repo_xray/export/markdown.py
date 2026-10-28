"""The documentation set: Markdown pages plus the SVG diagrams they show.

Everything lives under `architecture/`, ready to be copied to `docs/` in
the analysed repository. Images are embedded with `<picture>`, so GitHub
shows the dark version to readers who use the dark theme.
"""

import json
import re
import unicodedata
from dataclasses import asdict

from repo_xray.analysis.features import Feature
from repo_xray.analysis.flows import Flow
from repo_xray.analysis.layers import LAYERS
from repo_xray.analysis.stack import App
from repo_xray.pipeline import Analysis
from repo_xray.render.features import render_features
from repo_xray.render.flows import render_flow
from repo_xray.render.overview import render_overview
from repo_xray.render.theme import THEMES

FOLDER = "architecture"
FLOWS_PER_FEATURE = 3
KIND_NAMES = {"web": "web app", "api": "API", "mobile": "mobile app", "desktop": "desktop app", "library": "application"}

Bundle = dict[str, str | bytes]  # path inside the zip -> content


def build_documents(analysis: Analysis) -> Bundle:
    return _Writer(analysis).write()


def feature_page(feature_key: str) -> str:
    """Path of a feature's page inside the bundle."""
    return f"{FOLDER}/features/{_slug(feature_key)}.md"


class _Writer:
    def __init__(self, analysis: Analysis):
        self.a = analysis
        self.bundle: Bundle = {}
        self.slugs = {f.key: _slug(f.key) for f in analysis.features.features}

    def write(self) -> Bundle:
        stack = self.a.stack
        self._diagram("overview", lambda theme: render_overview(stack, self.a.files, theme))
        self._diagram("features", lambda theme: render_features(stack, self.a.features, theme))
        for flow in self._flows_to_draw():
            self._diagram(f"flow-{flow.key}", lambda theme, flow=flow: render_flow(flow, stack, theme))
        self.bundle[f"{FOLDER}/README.md"] = self._index()
        for feature in self.a.features.features:
            self.bundle[feature_page(feature.key)] = self._feature_page(feature)
        self.bundle[f"{FOLDER}/analysis.json"] = self._analysis_json()
        return self.bundle

    # Pages

    def _index(self) -> str:
        stack = self.a.stack
        lines = [f"# {stack.name} architecture", "", self._summary(), ""]
        lines += ["## What is it made of?", "", _picture("images/overview", f"{stack.name} overview"), ""]
        lines += ["## What does it do?", "", _picture("images/features", f"{stack.name} features"), ""]
        for app in self._apps_with_features():
            lines.append(f"**{app.name}** ({KIND_NAMES.get(app.kind, 'app')})")
            lines.append("")
            for feature in self.a.features.of_app(app.name):
                text = f" — {feature.description}" if feature.description else ""
                lines.append(f"- [{feature.name}](features/{self.slugs[feature.key]}.md){text}")
            lines.append("")
        if self.a.highlights:
            lines += ["## What happens when…?", ""]
            for flow in self.a.highlights:
                lines += [f"### {flow.title}", "", f"`{flow.method} {flow.route}`", "",
                          _picture(f"images/flow-{flow.key}", flow.title), ""]
        lines += ["---", "", "_Generated with repo-xray from the source code. "
                  "Diagrams show the main structure; small helpers are left out._", ""]
        return "\n".join(lines)

    def _feature_page(self, feature: Feature) -> str:
        app = next(a for a in self.a.stack.apps if a.name == feature.app)
        lines = [f"# {feature.name}", ""]
        if feature.description:
            lines += [f"> {feature.description}", ""]
        where = f"`{feature.path}`" if feature.path else "files grouped by name"
        lines += [f"Part of **{app.name}** ({KIND_NAMES.get(app.kind, 'app')}) · {where} · "
                  f"[back to the overview](../README.md)", ""]

        lines += ["## Layers", "", "| Layer | Files |", "| --- | ---: |"]
        for layer, label in LAYERS.items():
            if feature.layers.get(layer):
                lines.append(f"| {label} | {feature.layers[layer]} |")
        lines.append("")

        if feature.endpoints:
            lines += ["## Endpoints", "", "| Method | Route | What it does |", "| --- | --- | --- |"]
            for endpoint in feature.endpoints:
                lines.append(f"| `{endpoint.method}` | `{endpoint.path}` | {_cell(endpoint.summary or '')} |")
            lines.append("")

        relations = self._relations(feature)
        if relations:
            lines += ["## Connections", "", *relations, ""]

        flows = self._flows_of(feature)
        if flows:
            lines += ["## What happens when…?", ""]
            for flow in flows:
                lines += [f"### {flow.title}", "", f"`{flow.method} {flow.route}`", "",
                          _picture(f"../images/flow-{flow.key}", flow.title), ""]

        lines += ["## Files", "", f"<details><summary>{len(feature.files)} files</summary>", ""]
        lines += [f"- `{path}`" for path in feature.files]
        lines += ["", "</details>", ""]
        return "\n".join(lines)

    def _relations(self, feature: Feature) -> list[str]:
        names = {f.key: f for f in self.a.features.features}

        def link(key: str) -> str:
            return f"[{names[key].name}]({self.slugs[key]}.md) ({names[key].app})"

        lines = []
        if feature.calls:
            lines.append("- **Calls:** " + ", ".join(f"{link(k)} · {_calls(n)}" for k, n in _by_count(feature.calls)))
        callers = {f.key: f.calls[feature.key] for f in self.a.features.features if feature.key in f.calls}
        if callers:
            lines.append("- **Called from:** " + ", ".join(f"{link(k)} · {_calls(n)}" for k, n in _by_count(callers)))
        if feature.depends_on:
            lines.append("- **Depends on:** " + ", ".join(link(k) for k, _ in _by_count(feature.depends_on)))
        users = [f.key for f in self.a.features.features if feature.key in f.depends_on]
        if users:
            lines.append("- **Used by:** " + ", ".join(link(k) for k in users))
        if feature.services:
            lines.append("- **Services:** " + ", ".join(feature.services))
        return lines

    def _summary(self) -> str:
        stack = self.a.stack
        apps = [f"{_article(KIND_NAMES.get(a.kind, 'app'))} {KIND_NAMES.get(a.kind, 'app')} (`{a.name}`)"
                + (f" built with {_join(a.technologies[:2])}" if a.technologies else "") for a in stack.apps]
        text = f"{stack.name} is made of {_join(apps)}." if apps else f"{stack.name} has no recognisable app yet."
        databases = [s for s in stack.services if s.category == "database"]
        others = [s.name for s in stack.services if s.category != "database"]
        if databases:
            stored = _join([s.name + (f" ({', '.join(s.details)})" if s.details else "") for s in databases])
            text += f" It stores its data in {stored}"
            text += f" and relies on {_join(others)}." if others else "."
        elif others:
            text += f" It relies on {_join(others)}."
        count = len(self.a.features.features)
        if count > 1:
            text += f" The code is organised in {count} features, described below."
        return text

    # Diagrams

    def _diagram(self, name: str, render) -> None:
        for theme_name, theme in THEMES.items():
            self.bundle[f"{FOLDER}/images/{name}-{theme_name}.svg"] = render(theme)

    def _flows_to_draw(self) -> list[Flow]:
        drawn, seen = [], set()
        candidates = [*self.a.highlights, *[f for feature in self.a.features.features for f in self._flows_of(feature)]]
        for flow in candidates:
            if flow.key not in seen:
                seen.add(flow.key)
                drawn.append(flow)
        return drawn

    def _flows_of(self, feature: Feature) -> list[Flow]:
        related = [f for f in self.a.flows
                   if f.feature == feature.key or (f.steps and f.steps[0].feature == feature.key)]
        return sorted(related, key=lambda f: -f.score)[:FLOWS_PER_FEATURE]

    def _apps_with_features(self) -> list[App]:
        apps = [a for a in self.a.stack.apps if self.a.features.of_app(a.name)]
        return sorted(apps, key=lambda a: a.kind not in ("web", "mobile", "desktop"))

    def _analysis_json(self) -> str:
        data = {
            "schema_version": 1,
            "stack": asdict(self.a.stack),
            "features": [asdict(f) for f in self.a.features.features],
            "shared": [asdict(s) for s in self.a.features.shared],
            "flows": [asdict(f) for f in self.a.flows],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


def _picture(stem: str, alt: str) -> str:
    return (f'<picture>\n  <source media="(prefers-color-scheme: dark)" srcset="{stem}-dark.svg">\n'
            f'  <img alt="{_attribute(alt)}" src="{stem}-light.svg">\n</picture>')


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "feature"


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _calls(count: int) -> str:
    return f"{count} call" + ("" if count == 1 else "s")


def _by_count(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: -item[1])


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _attribute(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
