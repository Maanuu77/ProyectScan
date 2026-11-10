"""What the sidebar lists: every document of an analysis, grouped by level.

Plain data, built from an `Analysis` without any widget, so the order and
the grouping can be tested on their own:

    OVERVIEW   the architecture diagram, the summary page, the analysis report
    FEATURES   the feature map, then one page per feature, grouped by app
    FLOWS      the key flows, then the other drawn flows, grouped by feature
"""

from dataclasses import dataclass, field

from repo_xray.analysis.diagnostics import INFO
from repo_xray.export.markdown import FOLDER, feature_page, flow_diagram, flows_of
from repo_xray.pipeline import Analysis
from repo_xray.render import ids

DIAGRAM, PAGE, REPORT = "diagram", "page", "report"
SECTION, GROUP, ENTRY, NOTE = "section", "group", "entry", "note"
OVERVIEW, FEATURES, FLOWS = 1, 2, 3
LEVEL_TITLES = {OVERVIEW: "Overview", FEATURES: "Features", FLOWS: "Flows"}
LEVEL_QUESTIONS = {OVERVIEW: "What is it made of?", FEATURES: "What does it do?", FLOWS: "What happens when…?"}
CLIENT_KINDS = ("web", "mobile", "desktop")


@dataclass(frozen=True)
class Target:
    """A document the app can show."""

    kind: str  # DIAGRAM, PAGE or REPORT
    name: str = ""  # a diagram's name ("overview", "flow-post-api-orders") or a page's path in the bundle


OVERVIEW_DIAGRAM = Target(DIAGRAM, "overview")
FEATURES_DIAGRAM = Target(DIAGRAM, "features")
SUMMARY_PAGE = Target(PAGE, f"{FOLDER}/README.md")
REPORT_PAGE = Target(REPORT)


@dataclass
class NavItem:
    kind: str  # SECTION, GROUP, ENTRY or NOTE (a line that explains why a section is empty)
    title: str
    level: int = 0
    target: Target | None = None
    icon: str = ""
    badge: str = ""  # a count, or an HTTP method for flows
    badge_tone: str = ""  # "method", "warning" or "" for a plain count
    hint: str = ""  # shown as a tooltip
    keywords: str = ""  # extra text the filter matches, e.g. a flow's route


@dataclass
class Navigation:
    items: list[NavItem] = field(default_factory=list)

    def entries(self) -> list[NavItem]:
        return [item for item in self.items if item.kind == ENTRY]

    def find(self, target: Target) -> NavItem | None:
        return next((item for item in self.items if item.target == target), None)

    def home(self, level: int) -> Target | None:
        """The document a level opens with: its diagram, or its first flow."""
        return next((item.target for item in self.items if item.kind == ENTRY and item.level == level), None)

    def neighbour(self, target: Target, step: int) -> Target | None:
        """The entry `step` places after (or before) `target`, without wrapping around."""
        targets = [item.target for item in self.entries()]
        if target not in targets:
            return None
        index = targets.index(target) + step
        return targets[index] if 0 <= index < len(targets) else None

    def filtered(self, text: str) -> "Navigation":
        """Only the entries that match every word of `text`, with the headings they still need."""
        words = text.casefold().split()
        if not words:
            return self
        kept: list[NavItem] = []
        section: NavItem | None = None
        group: NavItem | None = None
        for item in self.items:
            if item.kind == SECTION:
                section, group = item, None
            elif item.kind == GROUP:
                group = item
            elif item.kind == ENTRY:
                haystack = f"{item.title} {item.keywords} {group.title if group else ''}".casefold()
                if all(word in haystack for word in words):
                    for heading in (section, group):
                        if heading is not None and heading not in kept:
                            kept.append(heading)
                    kept.append(item)
        return Navigation(kept)


def build(analysis: Analysis) -> Navigation:
    items: list[NavItem] = []
    items += _overview(analysis)
    items += _features(analysis)
    items += _flows(analysis)
    return Navigation(items)


def _overview(analysis: Analysis) -> list[NavItem]:
    problems = sum(1 for d in analysis.diagnostics if d.severity != INFO)
    notes = len(analysis.diagnostics)
    return [
        NavItem(SECTION, LEVEL_TITLES[OVERVIEW], OVERVIEW, hint=LEVEL_QUESTIONS[OVERVIEW]),
        NavItem(ENTRY, "Architecture", OVERVIEW, OVERVIEW_DIAGRAM, "layers", hint="Diagram: what the project is made of"),
        NavItem(ENTRY, "Summary", OVERVIEW, SUMMARY_PAGE, "page", hint="Page: the architecture in words",
                keywords="architecture overview readme page"),
        NavItem(ENTRY, "Analysis report", OVERVIEW, REPORT_PAGE, "report",
                badge=str(problems or notes or ""), badge_tone="warning" if problems else "",
                hint="What was read, the evidence behind each service and what could not be resolved",
                keywords="diagnostics warnings notes evidence"),
    ]


def _features(analysis: Analysis) -> list[NavItem]:
    features = analysis.features.features
    items = [NavItem(SECTION, LEVEL_TITLES[FEATURES], FEATURES, badge=str(len(features) or ""),
                     hint=LEVEL_QUESTIONS[FEATURES])]
    if not features:
        return [*items, NavItem(NOTE, "No features found", FEATURES,
                                hint="No application was recognised, so there is nothing to split into features.")]
    items.append(NavItem(ENTRY, "Feature map", FEATURES, FEATURES_DIAGRAM, "grid",
                         hint="Diagram: every feature and what it uses"))
    apps = sorted((a for a in analysis.stack.apps if analysis.features.of_app(a.name)),
                  key=lambda a: a.kind not in CLIENT_KINDS)  # the order of the feature map: frontends first
    for app in apps:
        items.append(NavItem(GROUP, app.name, FEATURES))
        for feature in analysis.features.of_app(app.name):
            items.append(NavItem(ENTRY, feature.name, FEATURES, Target(PAGE, feature_page(feature.key)), "page",
                                 hint=feature.description or "", keywords=f"{feature.key} {feature.description or ''}"))
    return items


def _flows(analysis: Analysis) -> list[NavItem]:
    items = [NavItem(SECTION, LEVEL_TITLES[FLOWS], FLOWS, hint=LEVEL_QUESTIONS[FLOWS])]
    if not analysis.flows:
        return [*items, NavItem(NOTE, "No flows found", FLOWS,
                                hint="Flows start at HTTP endpoints, and none was recognised in this project.")]
    seen = set()
    entries: list[NavItem] = []

    def add(flows, heading: str) -> None:
        fresh = [flow for flow in flows if flow.key not in seen]
        if not fresh:
            return
        entries.append(NavItem(GROUP, heading, FLOWS))
        for flow in fresh:
            seen.add(flow.key)
            entries.append(NavItem(ENTRY, flow.title, FLOWS, Target(DIAGRAM, flow_diagram(flow)), "flow",
                                   badge=flow.method, badge_tone="method", hint=f"{flow.method} {flow.route}",
                                   keywords=f"{flow.method} {flow.route}"))

    add(analysis.highlights, "Key flows")
    for feature in analysis.features.features:
        add(flows_of(analysis, feature), feature.name)
    items[0].badge = str(len(seen))
    return [*items, *entries]


def target_of_element(analysis: Analysis, element_id: str) -> Target | None:
    """Where a click on a named part of a diagram leads: a feature card to its page, an app to the feature map."""
    parsed = ids.parse(element_id)
    if parsed is None:
        return None
    kind, slug = parsed
    if kind == ids.FEATURE:
        feature = next((f for f in analysis.features.features if ids.slug(f.key) == slug), None)
        return Target(PAGE, feature_page(feature.key)) if feature else None
    if kind == ids.APP and analysis.features.features:
        return FEATURES_DIAGRAM
    if kind == ids.SERVICE:
        return REPORT_PAGE
    return None
