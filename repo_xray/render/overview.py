"""Level 1 diagram: "What is it made of?"

Three tiers read left to right, each in its own zone: what people use
(web, mobile, desktop), the backends behind it, and what those rely on,
with data stores told apart from external services. Services are ordered
to follow the apps that use them, so connectors rarely cross. A connector
that skips a tier leaves through the gap, travels along a lane above the
zones and comes back from the right; connectors to the same service share
one lane. Labels sit in the gaps between zones, never on top of a card,
and a gap too crowded to label keeps the colours and drops the words.
"""

from dataclasses import dataclass, field

from repo_xray import i18n
from repo_xray.analysis.linking import HttpLink
from repo_xray.analysis.stack import App, Service, Stack
from repo_xray.model import SourceFile
from repo_xray.render import components as c
from repo_xray.render import ids
from repo_xray.render import theme as t
from repo_xray.render.requests import CLIENT_KINDS, count_in_app, frontend_requests
from repo_xray.render.svg import Svg, fit_text, text_width, wrap_text

PAD = c.PAD
APP_WIDTH = 284
SERVICE_WIDTH = 252
ROW_GAP = 14  # between two cards of a zone
ZONE_GAP = 14  # between two zones of a tier
MIN_TIER_GAP = 92
USERS_HEIGHT = 32
USERS_SPACE = USERS_HEIGHT + 30  # the users marker plus the arrow below it
LANE_STEP = 16
MIN_WIDTH = 680
MAX_APPS = 5  # per tier; the rest are summarised in one card
MAX_SERVICES = 8
MAX_LABELS = 5  # connectors a gap can label before the words turn into noise

CATEGORY_ORDER = ["database", "cache", "search", "messaging", "auth", "storage", "platform", "external"]
DATA_CATEGORIES = ("database", "cache", "search", "messaging")  # where the project keeps or moves its data
CLIENT_VERBS = ("auth", "storage")  # what a frontend does with these differs from a backend


@dataclass
class _Box:
    key: str
    kind: str  # "app", "service" or "more"
    tier: int
    names: list[str] = field(default_factory=list)  # for "more": what the card stands for
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass
class _Zone:
    label: str
    keys: list[str]
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0


@dataclass
class _Edge:
    source: str
    target: str
    label: str
    accent: str | None = None  # accent of the service it reaches; None for app-to-app requests
    source_y: float = 0
    target_y: float = 0


@dataclass
class _Lane:
    """Connectors that skip a tier to reach the same card: they share one path around the zones."""

    target: str
    label: str
    accent: str | None
    sources: list[tuple[str, float]] = field(default_factory=list)  # (box key, height of its port)
    target_y: float = 0


def render_overview(stack: Stack, files: list[SourceFile], theme: t.Theme, lang: str = i18n.DEFAULT,
                    links: list[HttpLink] | None = None) -> str:
    """Draw the overview. With `links`, requests are counted per backend, as far as they could be matched."""
    return _OverviewRenderer(stack, files, theme, lang, links).render()


class _OverviewRenderer:
    def __init__(self, stack: Stack, files: list[SourceFile], theme: t.Theme, lang: str,
                 links: list[HttpLink] | None = None):
        self.stack = stack
        self.theme = theme
        self.lang = lang
        self.apps = {app.name: app for app in stack.apps}
        self.services = {service.name: service for service in stack.services}
        self.http_calls = {app.name: count_in_app(files, app, "http_calls") for app in stack.apps}
        self.endpoints = {app.name: count_in_app(files, app, "endpoints") for app in stack.apps}
        self.requests = frontend_requests(stack, files, links)
        self.lanes: list[_Lane] = []
        self.boxes: dict[str, _Box] = {}
        self.tiers: list[list[_Zone]] = []
        self.edges: list[_Edge] = []

    def render(self) -> str:
        self._build_tiers()
        self._build_edges()
        width, height, zones_top = self._place()
        svg = Svg(width, height, self.theme.background,
                  title=f"{self.stack.name}: {i18n.text(self.lang, 'overview')}",
                  description=self._description())
        self._draw_header(svg, width)
        if self.tiers:
            self._draw_users(svg, zones_top)
        for tier in self.tiers:
            for zone in tier:
                c.zone(svg, self.theme, zone.x, zone.y, zone.width, zone.height, zone.label)
        self._draw_edges(svg, zones_top)
        for box in self.boxes.values():
            if box.kind == "app":
                self._app_card(svg, self.apps[box.key[4:]], box)
            elif box.kind == "service":
                self._draw_service(svg, self.services[box.key[8:]], box)
            else:
                self._draw_more(svg, box)
        ci = "CI  ·  " + ", ".join(self.stack.ci) if self.stack.ci else None
        c.footer(svg, self.theme, width, height, ci, i18n.text(self.lang, "generated"))
        return svg.to_string()

    # What goes where

    def _build_tiers(self) -> None:
        clients = [a for a in self.stack.apps if a.kind in CLIENT_KINDS]
        backends = [a for a in self.stack.apps if a.kind not in CLIENT_KINDS]
        if clients:
            self.tiers.append([self._app_zone(i18n.text(self.lang, "tier.frontend"), clients)])
        if backends:
            only_apis = all(a.kind == "api" for a in backends)
            label = "tier.backend" if only_apis else "tier.application" if len(backends) == 1 else "tier.applications"
            self.tiers.append([self._app_zone(i18n.text(self.lang, label), backends)])

        shown, hidden = self._ranked_services()
        data = [s for s in shown if s.category in DATA_CATEGORIES]
        external = [s for s in shown if s.category not in DATA_CATEGORIES]
        zones = []
        if data:
            zones.append(_Zone(i18n.text(self.lang, "tier.data"), [self._add("service:" + s.name, "service") for s in data]))
        if external or hidden:
            keys = [self._add("service:" + s.name, "service") for s in external]
            if hidden:
                keys.append(self._add("more:services", "more", [s.name for s in hidden]))
            zones.append(_Zone(i18n.text(self.lang, "tier.services"), keys))
        if zones:
            self.tiers.append(zones)
        for index, tier in enumerate(self.tiers):
            for zone in tier:
                for key in zone.keys:
                    self.boxes[key].tier = index

    def _app_zone(self, label: str, apps: list[App]) -> _Zone:
        shown = apps
        if len(apps) > MAX_APPS:
            shown = sorted(apps, key=lambda a: -a.lines)[:MAX_APPS - 1]
            shown = [a for a in apps if a in shown]  # keep the project's own order
        keys = [self._add("app:" + a.name, "app") for a in shown]
        if len(shown) < len(apps):
            keys.append(self._add(f"more:{label}", "more", [a.name for a in apps if a not in shown]))
        return _Zone(label, keys)

    def _add(self, key: str, kind: str, names: list[str] | None = None) -> str:
        self.boxes[key] = _Box(key=key, kind=kind, tier=0, names=names or [])
        return key

    def _ranked_services(self) -> tuple[list[Service], list[Service]]:
        """Services in drawing order, and the ones left for the "more" card when there are too many.

        Each service sits near the apps that use it (the average position of its users), which is
        what keeps connectors from crossing; those a frontend reaches directly come first, next to
        the lane their connector arrives by.
        """
        position = {app.name: index for index, app in enumerate(
            [a for a in self.stack.apps if a.kind not in CLIENT_KINDS])}
        clients = {a.name for a in self.stack.apps if a.kind in CLIENT_KINDS}

        def key(service: Service):
            users = [position[u] for u in service.used_by if u in position]
            category = CATEGORY_ORDER.index(service.category) if service.category in CATEGORY_ORDER else 99
            return (not any(u in clients for u in service.used_by),
                    sum(users) / len(users) if users else 99, category, service.name)

        services = list(self.stack.services)
        if len(services) > MAX_SERVICES:
            kept = sorted(services, key=lambda s: (-len(s.used_by), key(s)))[:MAX_SERVICES - 1]
            return sorted(kept, key=key), sorted((s for s in services if s not in kept), key=key)
        return sorted(services, key=key), []

    def _build_edges(self) -> None:
        clients = [a for a in self.stack.apps if a.kind in CLIENT_KINDS and "app:" + a.name in self.boxes]
        apis = [a for a in self.stack.apps if a.kind == "api" and "app:" + a.name in self.boxes]
        for client in clients:
            for api in apis:
                if (client.name, api.name) in self.requests:
                    self.edges.append(_Edge("app:" + client.name, "app:" + api.name, self._request_label(client, api)))
        for service in self.stack.services:
            if "service:" + service.name not in self.boxes:
                continue
            for user in service.used_by:
                if "app:" + user in self.boxes:
                    self.edges.append(_Edge("app:" + user, "service:" + service.name,
                                            self._verb(service, self.apps[user]), service.category))

    def _request_label(self, client: App, api: App) -> str:
        """What to write on the connector from a frontend to a backend: the count when there is one to trust."""
        calls = self.requests[(client.name, api.name)]
        if calls:
            return f"REST · {i18n.count(self.lang, calls, 'call')}"
        return "REST" if self.http_calls[client.name] else "HTTP"

    def _verb(self, service: Service, user: App) -> str:
        category = service.category if f"verb.{service.category}" in i18n.TEXTS else "platform"
        if user.kind in CLIENT_KINDS and category in CLIENT_VERBS:
            return i18n.text(self.lang, f"verb.client.{category}")
        return i18n.text(self.lang, f"verb.{category}")

    def _is_lane(self, edge: _Edge) -> bool:
        """Whether the edge skips a tier, so it must go around the cards instead of between them."""
        return self.boxes[edge.target].tier - self.boxes[edge.source].tier > 1

    # Layout

    def _place(self) -> tuple[float, float, float]:
        for box in self.boxes.values():
            if box.kind == "app":
                box.width = APP_WIDTH
                box.height = self._app_card(None, self.apps[box.key[4:]], _Box("", "app", 0, width=APP_WIDTH))
            elif box.kind == "service":
                box.width = SERVICE_WIDTH
                box.height = 90 if self.services[box.key[8:]].details else 72
            else:
                box.width = SERVICE_WIDTH if box.key == "more:services" else APP_WIDTH
                box.height = 44 + 18 * len(self._more_lines(box))

        for tier in self.tiers:
            for zone in tier:
                zone.width = max(self.boxes[k].width for k in zone.keys) + c.ZONE_PAD * 2
                zone.height = (c.ZONE_HEADER + sum(self.boxes[k].height for k in zone.keys)
                               + ROW_GAP * (len(zone.keys) - 1) + c.ZONE_PAD)
        gaps = []
        for index in range(len(self.tiers) - 1):
            labels = [e.label for e in self.edges if not self._is_lane(e) and self.boxes[e.source].tier == index]
            widest = max((c.pill_width(label) for label in labels), default=0)
            gaps.append(max(MIN_TIER_GAP, widest + 44))

        self._build_lanes()
        lane_space = len(self.lanes) * LANE_STEP + 14 if self.lanes else 0
        if self.lanes:
            gaps[0] += lane_space  # the lanes leave the first tier through the gap after it
        tiers_width = sum(max(z.width for z in tier) for tier in self.tiers) + sum(gaps)
        width = max(PAD * 2 + tiers_width + lane_space, MIN_WIDTH)

        description = self._description_lines(width)
        zones_top = (c.header_bottom() + (26 + 20 * len(description) if description else 0) + 30
                     + (USERS_SPACE + lane_space if self.tiers else 0))
        heights = [sum(z.height for z in tier) + ZONE_GAP * (len(tier) - 1) for tier in self.tiers]
        content_height = max(heights, default=0)

        x = PAD + (width - PAD * 2 - tiers_width - lane_space) / 2
        for index, tier in enumerate(self.tiers):
            tier_width = max(z.width for z in tier)
            extra = (content_height - heights[index]) / len(tier)  # every tier ends on the same line
            y = zones_top
            for zone in tier:
                zone.x, zone.y, zone.width, zone.height = x, y, tier_width, zone.height + extra
                self._place_cards(zone)
                y += zone.height + ZONE_GAP
            x += tier_width + (gaps[index] if index < len(gaps) else 0)
        self._place_ports()
        height = zones_top + content_height + (c.FOOTER_SPACE if self.tiers else 26 + PAD)
        return width, height, zones_top

    def _place_cards(self, zone: _Zone) -> None:
        """Stack the zone's cards, centred in the room under its caption."""
        cards = sum(self.boxes[k].height for k in zone.keys) + ROW_GAP * (len(zone.keys) - 1)
        room = zone.height - c.ZONE_HEADER - c.ZONE_PAD
        y = zone.y + c.ZONE_HEADER + (room - cards) / 2
        for key in zone.keys:
            box = self.boxes[key]
            box.x, box.y = zone.x + (zone.width - box.width) / 2, y
            y += box.height + ROW_GAP

    def _build_lanes(self) -> None:
        """One lane per card reached across a tier, the highest card on the innermost lane so lanes never cross."""
        by_target: dict[str, _Lane] = {}
        for edge in self.edges:
            if self._is_lane(edge):
                lane = by_target.setdefault(edge.target, _Lane(edge.target, edge.label, edge.accent))
                lane.sources.append((edge.source, 0))
        order = [key for tier in self.tiers for zone in tier for key in zone.keys]
        self.lanes = sorted(by_target.values(), key=lambda lane: order.index(lane.target))

    def _place_ports(self) -> None:
        """Where each connector leaves and arrives: spread along the card's side, in the order of the other end."""
        direct = [e for e in self.edges if not self._is_lane(e)]
        for box in self.boxes.values():
            leaving = sorted((e for e in direct if e.source == box.key), key=lambda e: self.boxes[e.target].cy)
            step = min(22, (box.height - 40) / max(len(leaving) - 1, 1))
            for index, edge in enumerate(leaving):
                edge.source_y = box.cy + (index - (len(leaving) - 1) / 2) * step
        for box in self.boxes.values():
            arriving = sorted((e for e in direct if e.target == box.key), key=lambda e: e.source_y)
            lanes = [lane for lane in self.lanes if lane.target == box.key]
            count = len(arriving) + len(lanes)
            step = min(14, (box.height - 28) / max(count - 1, 1))
            for index, edge in enumerate(arriving):
                edge.target_y = box.cy + (index - (count - 1) / 2) * step
            for index, lane in enumerate(lanes, start=len(arriving)):
                lane.target_y = box.cy + (index - (count - 1) / 2) * step
        # Lanes leave from the top of the card's side, above the connectors to the next tier.
        used: dict[str, int] = {}
        for lane in self.lanes:
            ports = []
            for key, _ in lane.sources:
                ports.append((key, self.boxes[key].y + 20 + used.get(key, 0) * 12))
                used[key] = used.get(key, 0) + 1
            lane.sources = ports

    # Header and users

    def _draw_header(self, svg: Svg, width: float) -> None:
        th, lang = self.theme, self.lang
        y = c.header(svg, th, 1, i18n.text(lang, "kicker.overview"), c.title_lines(self.stack.name, width))
        lines = sum(a.lines for a in self.stack.apps)
        facts = [i18n.count(lang, len(self.stack.apps), "app")]
        if self.stack.services:
            facts.append(i18n.count(lang, len(self.stack.services), "service"))
        facts.append(i18n.count(lang, lines, "lines_of_code", _compact(lines)))
        svg.text(PAD, y, "  ·  ".join(facts), t.BODY, th.text_muted)
        for index, line in enumerate(self._description_lines(width)):
            svg.text(PAD, y + 26 + index * 20, line, t.BODY, th.text)

    def _description_lines(self, width: float) -> list[str]:
        if not self.stack.description:
            return []
        return wrap_text(self.stack.description, max(width - PAD * 2, 400), t.BODY, max_lines=2)

    def _draw_users(self, svg: Svg, zones_top: float) -> None:
        """People come in through the first tier: a marker above it and an arrow into it."""
        th = self.theme
        first = self.tiers[0][0]
        label = i18n.text(self.lang, "users")
        width = text_width(label, t.BODY, 600) + 52
        top = zones_top - USERS_SPACE - (len(self.lanes) * LANE_STEP + 14 if self.lanes else 0)
        cx = first.x + min(first.width / 2, 110)
        svg.rect(cx - width / 2, top, width, USERS_HEIGHT, USERS_HEIGHT / 2, fill=th.surface, stroke=th.border,
                 stroke_width=1)
        t.icon(svg, "users", cx - width / 2 + 13, top + 8, 16, th.text_muted)
        svg.text(cx - width / 2 + 36, top + 20.5, label, t.BODY, th.text, weight=600)
        c.polyline(svg, [(cx, top + USERS_HEIGHT + 5), (cx, zones_top - 3)], th.connector)

    # Connectors

    def _draw_edges(self, svg: Svg, zones_top: float) -> None:
        th = self.theme
        direct = [e for e in self.edges if not self._is_lane(e)]
        crowded = {tier for tier in range(len(self.tiers))
                   if sum(1 for e in direct if self.boxes[e.source].tier == tier) > MAX_LABELS}
        lane_room = len(self.lanes) * LANE_STEP + 14 if self.lanes else 0
        labels: list[tuple[float, float, str]] = []
        for edge in direct:
            source, target = self.boxes[edge.source], self.boxes[edge.target]
            colour = th.accent(edge.accent).strong if edge.accent else th.connector
            x1, x2 = source.right + 2, target.x - 3
            svg.group_start(opacity=0.75 if edge.accent else None)
            c.curve(svg, x1, edge.source_y, x2, edge.target_y, colour, width=1.5 if edge.accent else 1.75)
            svg.group_end()
            if source.tier in crowded and edge.accent:
                continue  # the service's card already says what it is; its colour ties the line to it
            # The label sits in the gap between the two zones, where nothing else is drawn.
            source_zone = self.tiers[source.tier][0]
            left = source_zone.x + source_zone.width + (lane_room if source.tier == 0 else 0)
            gap_x = (left + self.tiers[target.tier][0].x) / 2
            labels.append((gap_x, _curve_y_at(x1, edge.source_y, x2, edge.target_y, gap_x), edge.label))
        self._draw_lanes(svg, zones_top)
        for x, y, label in _spread(labels):
            c.pill(svg, th, x, y, label)

    def _draw_lanes(self, svg: Svg, zones_top: float) -> None:
        """Connectors that skip a tier: out through the gap, over the zones and back in from the right."""
        th = self.theme
        if not self.lanes:
            return
        first = self.tiers[0][0]
        middle = self.tiers[1][0]
        right = max(z.x + z.width for tier in self.tiers for z in tier)
        count = len(self.lanes)
        for index, lane in enumerate(self.lanes):
            colour = th.accent(lane.accent).strong if lane.accent else th.connector
            target = self.boxes[lane.target]
            lane_y = zones_top - 16 - index * LANE_STEP
            side_x = right + 14 + index * LANE_STEP
            channel_x = first.x + first.width + 12 + (count - 1 - index) * LANE_STEP  # the lowest lane turns last
            ports = sorted(lane.sources, key=lambda port: -port[1])
            svg.group_start(opacity=0.8 if lane.accent else None)
            for key, port_y in ports[1:]:  # the others join the path the lowest source starts
                c.polyline(svg, [(self.boxes[key].right + 2, port_y), (channel_x, port_y)], colour, dashed=True,
                           arrow=False)
            key, port_y = ports[0]
            c.polyline(svg, [(self.boxes[key].right + 2, port_y), (channel_x, port_y), (channel_x, lane_y),
                             (side_x, lane_y), (side_x, lane.target_y), (target.right + 3, lane.target_y)],
                       colour, dashed=True)
            svg.group_end()
            c.pill(svg, th, middle.x + middle.width * (index + 1) / (count + 1), lane_y, lane.label)

    # Cards

    def _app_card(self, svg: Svg | None, app: App, box: _Box) -> float:
        """Draw the card, or only measure it when `svg` is None. Returns its height."""
        th = self.theme
        accent = th.accent(app.kind)
        x, y, w = box.x, box.y, box.width
        inner = w - 32

        if svg is not None:
            c.card(svg, th, x, y, w, box.height, ids.app_id(app.name))
            c.icon_tile(svg, th, app.kind, x + 16, y + 16, 40)
            svg.text(x + 68, y + 31, i18n.text(self.lang, f"kind.{app.kind}"), t.LABEL, accent.strong, weight=700,
                     letter_spacing=0.8)
            svg.text(x + 68, y + 51, fit_text(app.name, w - 84, t.HEADING, 700), t.HEADING, th.text, weight=700)

        # Technology chips, wrapped to the card width.
        chip_x, chip_y = x + 16, y + 72
        for tech in app.technologies:
            tech = fit_text(tech, inner - 18, t.SMALL)
            chip_w = c.chip_width(tech)
            if chip_x + chip_w > x + 16 + inner and chip_x > x + 16:
                chip_x, chip_y = x + 16, chip_y + c.CHIP_HEIGHT + c.CHIP_GAP
            if svg is not None:
                c.chip(svg, th, chip_x, chip_y, tech)
            chip_x += chip_w + c.CHIP_GAP
        cursor = chip_y + c.CHIP_HEIGHT + 24 if app.technologies else y + 86

        # What it holds: each number stands out, and the row wraps when the language makes it longer.
        stat_x = x + 16
        for value, label in self._stats(app):
            needed = c.stat_width(value, label)
            if stat_x + needed > x + 16 + inner and stat_x > x + 16:
                stat_x, cursor = x + 16, cursor + 20
            if svg is not None:
                c.stat(svg, th, stat_x, cursor, value, label)
            stat_x += needed + 16

        if not app.deployments:
            return cursor + 18 - y
        separator = cursor + 16
        if svg is not None:
            svg.line(x + 1, separator, x + w - 1, separator, stroke=th.border, stroke_width=1)
            t.icon(svg, "deploy", x + 16, separator + 11, 16, th.text_muted)
            svg.text(x + 40, separator + 24, fit_text(_deployment_text(app.deployments), inner - 26, t.SMALL),
                     t.SMALL, th.text_muted)
        return separator + 38 - y

    def _stats(self, app: App) -> list[tuple[str, str]]:
        counted = [i18n.count(self.lang, app.files, "file"), i18n.count(self.lang, app.lines, "lines", _compact(app.lines))]
        if self.endpoints[app.name]:
            counted.append(i18n.count(self.lang, self.endpoints[app.name], "endpoint"))
        return [(value, label) for value, _, label in (text.partition(" ") for text in counted)]

    def _draw_service(self, svg: Svg, service: Service, box: _Box) -> None:
        th = self.theme
        accent = th.accent(service.category)
        x, y, w = box.x, box.y, box.width
        c.card(svg, th, x, y, w, box.height, ids.service_id(service.name))
        c.icon_tile(svg, th, service.category, x + 16, y + 16, 40)
        svg.text(x + 68, y + 33, fit_text(service.name, w - 82, t.SUBHEADING, 700), t.SUBHEADING, th.text, weight=700)
        key = f"category.{service.category}"
        category = i18n.text(self.lang, key if key in i18n.TEXTS else "category.other")
        svg.text(x + 68, y + 52, fit_text(category, w - 82, t.SMALL), t.SMALL, th.text_muted)
        if service.details:
            details = "  ·  ".join(service.details)
            svg.text(x + 68, y + 72, fit_text(details, w - 82, t.SMALL, 600), t.SMALL, accent.strong, weight=600)

    def _more_lines(self, box: _Box) -> list[str]:
        return wrap_text(", ".join(box.names), box.width - 32, t.SMALL, max_lines=4)

    def _draw_more(self, svg: Svg, box: _Box) -> None:
        """What did not fit as cards of its own, by name, so nothing is silently left out."""
        th = self.theme
        c.card(svg, th, box.x, box.y, box.width, box.height, dashed=True, muted=True)
        svg.text(box.x + 16, box.y + 27, i18n.text(self.lang, "more", n=len(box.names)), t.BODY, th.text_muted,
                 weight=700)
        for index, line in enumerate(self._more_lines(box)):
            svg.text(box.x + 16, box.y + 47 + index * 18, line, t.SMALL, th.text_subtle)

    def _description(self) -> str:
        lang = self.lang
        apps = ", ".join(f"{a.name} ({i18n.text(lang, f'kind_name.{a.kind}')}, {', '.join(a.technologies[:2])})"
                         for a in self.stack.apps)
        services = ", ".join(s.name for s in self.stack.services) or i18n.text(lang, "no_services")
        return i18n.text(lang, "overview.description", name=self.stack.name, apps=apps, services=services)


def _curve_y_at(x1: float, y1: float, x2: float, y2: float, x: float) -> float:
    """Height of the connector from (x1, y1) to (x2, y2) where it crosses the vertical at `x`."""
    low, high = 0.0, 1.0
    for _ in range(24):  # x grows with u along the curve, so bisection finds it
        middle = (low + high) / 2
        if c.curve_point(x1, y1, x2, y2, middle)[0] < x:
            low = middle
        else:
            high = middle
    return c.curve_point(x1, y1, x2, y2, (low + high) / 2)[1]


def _spread(labels: list[tuple[float, float, str]], minimum: float = c.PILL_HEIGHT + 4) -> list[tuple[float, float, str]]:
    """Move labels that share a gap apart, so none covers another; their order from top to bottom is kept."""
    placed: list[tuple[float, float, str]] = []
    for x, y, label in sorted(labels, key=lambda item: (item[0], item[1])):
        if placed and placed[-1][0] == x and y - placed[-1][1] < minimum:
            y = placed[-1][1] + minimum
        placed.append((x, y, label))
    return placed


def _deployment_text(deployments: list[str]) -> str:
    targets = [d for d in deployments if d != "Docker"]
    if not targets:
        return "Docker"
    text = " · ".join(targets)
    return f"{text}  (Docker)" if "Docker" in deployments else text


def _compact(number: int) -> str:
    return f"{number / 1000:.1f}k" if number >= 1000 else str(number)
