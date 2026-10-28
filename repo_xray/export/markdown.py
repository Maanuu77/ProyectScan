"""The documentation set: Markdown pages plus the SVG diagrams they show.

Everything lives under `architecture/`, ready to be copied to `docs/` in
the analysed repository. Images are embedded with `<picture>`, so GitHub
shows the dark version to readers who use the dark theme.
"""

import json
import re
import unicodedata
from dataclasses import asdict

from repo_xray import i18n
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

Bundle = dict[str, str | bytes]  # path inside the zip -> content


def build_documents(analysis: Analysis) -> Bundle:
    return _Writer(analysis).write()


def summary(analysis: Analysis) -> str:
    """The opening paragraphs: what the project is about, then what it is made of."""
    return _Writer(analysis).summary()


def feature_page(feature_key: str) -> str:
    """Path of a feature's page inside the bundle."""
    return f"{FOLDER}/features/{_slug(feature_key)}.md"


class _Writer:
    def __init__(self, analysis: Analysis):
        self.a = analysis
        self.lang = analysis.language
        self.bundle: Bundle = {}
        self.slugs = {f.key: _slug(f.key) for f in analysis.features.features}

    def write(self) -> Bundle:
        stack, lang = self.a.stack, self.lang
        self._diagram("overview", lambda theme: render_overview(stack, self.a.files, theme, lang))
        self._diagram("features", lambda theme: render_features(stack, self.a.features, theme, lang))
        for flow in self._flows_to_draw():
            self._diagram(f"flow-{flow.key}", lambda theme, flow=flow: render_flow(flow, stack, theme, lang))
        self.bundle[f"{FOLDER}/README.md"] = self._index()
        for feature in self.a.features.features:
            self.bundle[feature_page(feature.key)] = self._feature_page(feature)
        self.bundle[f"{FOLDER}/analysis.json"] = self._analysis_json()
        return self.bundle

    # Pages

    def _index(self) -> str:
        stack, tr = self.a.stack, self._text
        lines = [f"# {tr('page.title', name=stack.name)}", "", self.summary(), ""]
        lines += [f"## {tr('page.made_of')}", "", _picture("images/overview", tr("page.alt_overview", name=stack.name)), ""]
        lines += [f"## {tr('page.does')}", "", _picture("images/features", tr("page.alt_features", name=stack.name)), ""]
        for app in self._apps_with_features():
            lines.append(f"**{app.name}** ({tr(f'kind_name.{app.kind}')})")
            lines.append("")
            for feature in self.a.features.of_app(app.name):
                text = f" — {feature.description}" if feature.description else ""
                lines.append(f"- [{feature.name}](features/{self.slugs[feature.key]}.md){text}")
            lines.append("")
        if self.a.highlights:
            lines += [f"## {tr('page.happens')}", ""]
            for flow in self.a.highlights:
                lines += [f"### {flow.title}", "", f"`{flow.method} {flow.route}`", "",
                          _picture(f"images/flow-{flow.key}", flow.title), ""]
        lines += ["---", "", tr("page.footer"), ""]
        return "\n".join(lines)

    def _text(self, key: str, **values) -> str:
        return i18n.text(self.lang, key, **values)

    def _feature_page(self, feature: Feature) -> str:
        tr = self._text
        app = next(a for a in self.a.stack.apps if a.name == feature.app)
        lines = [f"# {feature.name}", ""]
        if feature.description:
            lines += [f"> {feature.description}", ""]
        where = f"`{feature.path}`" if feature.path else tr("page.grouped_by_name")
        lines += [tr("page.part_of", app=app.name, kind=tr(f"kind_name.{app.kind}"), where=where), ""]

        lines += [f"## {tr('page.layers')}", "", tr("page.layer_table"), "| --- | ---: |"]
        for layer in LAYERS:
            if feature.layers.get(layer):
                lines.append(f"| {tr(f'layer.{layer}')} | {feature.layers[layer]} |")
        lines.append("")

        if feature.endpoints:
            lines += [f"## {tr('page.endpoints')}", "", tr("page.endpoint_table"), "| --- | --- | --- |"]
            for endpoint in feature.endpoints:
                lines.append(f"| `{endpoint.method}` | `{endpoint.path}` | {_cell(endpoint.summary or '')} |")
            lines.append("")

        relations = self._relations(feature)
        if relations:
            lines += [f"## {tr('page.connections')}", "", *relations, ""]

        flows = self._flows_of(feature)
        if flows:
            lines += [f"## {tr('page.happens')}", ""]
            for flow in flows:
                lines += [f"### {flow.title}", "", f"`{flow.method} {flow.route}`", "",
                          _picture(f"../images/flow-{flow.key}", flow.title), ""]

        files = i18n.count(self.lang, len(feature.files), "file")
        lines += [f"## {tr('page.files')}", "", f"<details><summary>{files}</summary>", ""]
        lines += [f"- `{path}`" for path in feature.files]
        lines += ["", "</details>", ""]
        return "\n".join(lines)

    def _relations(self, feature: Feature) -> list[str]:
        names = {f.key: f for f in self.a.features.features}

        def link(key: str) -> str:
            return f"[{names[key].name}]({self.slugs[key]}.md) ({names[key].app})"

        def calls(n: int) -> str:
            return i18n.count(self.lang, n, "call")

        def item(label_key: str, values: list[str]) -> str:
            return f"- **{self._text(label_key)}:** " + ", ".join(values)

        lines = []
        if feature.calls:
            lines.append(item("page.calls", [f"{link(k)} · {calls(n)}" for k, n in _by_count(feature.calls)]))
        callers = {f.key: f.calls[feature.key] for f in self.a.features.features if feature.key in f.calls}
        if callers:
            lines.append(item("page.called_from", [f"{link(k)} · {calls(n)}" for k, n in _by_count(callers)]))
        if feature.depends_on:
            lines.append(item("page.depends_on", [link(k) for k, _ in _by_count(feature.depends_on)]))
        users = [f.key for f in self.a.features.features if feature.key in f.depends_on]
        if users:
            lines.append(item("page.used_by", [link(k) for k in users]))
        if feature.services:
            lines.append(item("page.services", feature.services))
        return lines

    def summary(self) -> str:
        description = self.a.stack.description
        return f"> {description}\n\n{self._structure()}" if description else self._structure()

    def _structure(self) -> str:
        stack, tr, lang = self.a.stack, self._text, self.lang
        apps = []
        for a in stack.apps:
            kind = tr(f"kind_name.{a.kind}")
            entry = tr("summary.app", article=_article(kind), kind=kind, app=a.name)
            if a.technologies:
                entry += tr("summary.built_with", techs=i18n.join(lang, a.technologies[:2]))
            apps.append(entry)
        text = (tr("summary.made_of", name=stack.name, apps=i18n.join(lang, apps)) if apps
                else tr("summary.no_app", name=stack.name))
        databases = [s for s in stack.services if s.category == "database"]
        others = [s.name for s in stack.services if s.category != "database"]
        if databases:
            stored = i18n.join(lang, [s.name + (f" ({', '.join(s.details)})" if s.details else "") for s in databases])
            text += tr("summary.stores", stores=stored)
            text += tr("summary.and_relies", others=i18n.join(lang, others)) if others else "."
        elif others:
            text += tr("summary.relies", others=i18n.join(lang, others))
        count = len(self.a.features.features)
        if count > 1:
            text += tr("summary.features", n=count)
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


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _by_count(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: -item[1])


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _attribute(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
