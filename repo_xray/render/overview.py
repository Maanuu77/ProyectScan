"""Level 1 diagram: "What is it made of?"

Three columns read left to right: what people use (web, mobile, desktop),
the backends behind it, and the services they rely on. A "Users" marker
sits above the first column, and a connector that skips a column travels
along a lane above the cards so it never crosses one.
"""

from dataclasses import dataclass, field

from repo_xray.analysis.paths import is_inside, is_test_path
from repo_xray.analysis.stack import App, Service, Stack
from repo_xray.model import SourceFile
from repo_xray.render import theme as t
from repo_xray.render.svg import Svg, fit_text, text_width

PAD = 40
APP_WIDTH = 270
SERVICE_WIDTH = 244
ROW_GAP = 22
MIN_COLUMN_GAP = 76
USERS_SPACE = 92  # users marker plus the arrow below it
LANE_STEP = 14
MIN_WIDTH = 640

CLIENT_KINDS = ("web", "mobile", "desktop")
KIND_LABELS = {"web": "WEB APP", "api": "API", "mobile": "MOBILE APP", "desktop": "DESKTOP APP",
               "library": "APPLICATION"}
CATEGORY_LABELS = {"database": "Database", "auth": "Authentication", "storage": "File storage",
                   "cache": "Cache", "messaging": "Messaging", "search": "Search",
                   "platform": "Platform", "external": "External API"}
CATEGORY_ORDER = list(CATEGORY_LABELS)
SERVICE_VERBS = {"database": "reads & writes", "auth": "verifies users", "storage": "stores files",
                 "cache": "caches", "messaging": "publishes events", "search": "indexes",
                 "platform": "uses", "external": "calls"}
CLIENT_VERBS = {**SERVICE_VERBS, "auth": "signs in", "storage": "uploads files"}


@dataclass
class _Box:
    key: str
    column: int
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
class _Edge:
    source: str
    target: str
    label: str


@dataclass
class _Layout:
    boxes: dict[str, _Box] = field(default_factory=dict)
    columns: list[list[str]] = field(default_factory=list)
    edges: list[_Edge] = field(default_factory=list)


def render_overview(stack: Stack, files: list[SourceFile], theme: t.Theme) -> str:
    return _OverviewRenderer(stack, files, theme).render()


class _OverviewRenderer:
    def __init__(self, stack: Stack, files: list[SourceFile], theme: t.Theme):
        self.stack = stack
        self.theme = theme
        self.apps = {app.name: app for app in stack.apps}
        self.services = {service.name: service for service in stack.services}
        self.http_calls = {app.name: _count(files, app, "http_calls") for app in stack.apps}
        self.endpoints = {app.name: _count(files, app, "endpoints") for app in stack.apps}

    # Layout

    def render(self) -> str:
        layout = self._columns()
        self._edges(layout)
        width, height, content_top = self._place(layout)
        svg = Svg(width, height, self.theme.background,
                  title=f"{self.stack.name} architecture overview",
                  description=self._description())
        self._draw_header(svg, width)
        clients = layout.columns[0] if layout.columns else []
        if clients:
            self._draw_users(svg, layout, clients)
        self._draw_edges(svg, layout, content_top)
        for key, box in layout.boxes.items():
            if key in self.apps:
                self._draw_app(svg, self.apps[key], box)
            else:
                self._draw_service(svg, self.services[key], box)
        self._draw_footer(svg, width, height)
        return svg.to_string()

    def _columns(self) -> _Layout:
        layout = _Layout()
        clients = [a.name for a in self.stack.apps if a.kind in CLIENT_KINDS]
        backends = [a.name for a in self.stack.apps if a.kind not in CLIENT_KINDS]
        client_services = {s.name for s in self.stack.services if any(u in clients for u in s.used_by)}
        services = sorted(self.services, key=lambda name: (
            name not in client_services,
            CATEGORY_ORDER.index(self.services[name].category) if self.services[name].category in CATEGORY_ORDER else 99,
            name,
        ))
        for group in (clients, backends, services):
            if group:
                layout.columns.append(group)
        for index, column in enumerate(layout.columns):
            for key in column:
                layout.boxes[key] = _Box(key=key, column=index)
        return layout

    def _edges(self, layout: _Layout) -> None:
        clients = [a for a in self.stack.apps if a.kind in CLIENT_KINDS]
        apis = [a for a in self.stack.apps if a.kind == "api"]
        for client in clients:
            for api in apis:
                calls = self.http_calls[client.name]
                if calls or len(apis) == 1:
                    label = f"REST · {calls} calls" if calls else "HTTP"
                    layout.edges.append(_Edge(client.name, api.name, label))
        for service in self.stack.services:
            for user in service.used_by:
                if user in self.apps:
                    verbs = CLIENT_VERBS if self.apps[user].kind in CLIENT_KINDS else SERVICE_VERBS
                    layout.edges.append(_Edge(user, service.name, verbs.get(service.category, "uses")))

    def _place(self, layout: _Layout) -> tuple[float, float, float]:
        for key, box in layout.boxes.items():
            box.width = APP_WIDTH if key in self.apps else SERVICE_WIDTH
            box.height = self._app_height(self.apps[key]) if key in self.apps else self._service_height(key)

        gaps = []
        for index in range(len(layout.columns) - 1):
            labels = [e.label for e in layout.edges
                      if layout.boxes[e.source].column == index and layout.boxes[e.target].column == index + 1]
            widest = max((text_width(label, t.LABEL) + 18 for label in labels), default=0)
            gaps.append(max(MIN_COLUMN_GAP, widest + 44))

        lanes = self._lane_edges(layout)
        header_bottom = PAD + 66
        has_users = bool(layout.columns)
        content_top = header_bottom + (USERS_SPACE if has_users else 24) + (len(lanes) * LANE_STEP if lanes else 0)
        heights = [sum(layout.boxes[k].height for k in column) + ROW_GAP * (len(column) - 1)
                   for column in layout.columns]
        content_height = max(heights, default=0)

        x = PAD
        for index, column in enumerate(layout.columns):
            column_height = heights[index]
            y = content_top + (content_height - column_height) / 2
            for key in column:
                box = layout.boxes[key]
                box.x, box.y = x, y
                y += box.height + ROW_GAP
            x += max(layout.boxes[k].width for k in column) + (gaps[index] if index < len(gaps) else 0)

        right_lanes = len(lanes) * LANE_STEP + (20 if lanes else 0)
        width = x + PAD + right_lanes
        if width < MIN_WIDTH:
            for box in layout.boxes.values():
                box.x += (MIN_WIDTH - width) / 2
            width = MIN_WIDTH
        height = content_top + content_height + 88
        return width, height, content_top

    def _lane_edges(self, layout: _Layout) -> list[_Edge]:
        return [e for e in layout.edges if layout.boxes[e.target].column - layout.boxes[e.source].column > 1]

    def _service_height(self, name: str) -> float:
        return 88 if self.services[name].details else 70

    def _app_height(self, app: App) -> float:
        return self._app_card(None, app, _Box("", 0, 0, 0, APP_WIDTH, 0))

    # Drawing

    def _draw_header(self, svg: Svg, width: float) -> None:
        th = self.theme
        svg.text(PAD, PAD + 24, self.stack.name, t.TITLE, th.text, weight=700)
        lines = sum(a.lines for a in self.stack.apps)
        facts = [_plural(len(self.stack.apps), "app")]
        if self.stack.services:
            facts.append(_plural(len(self.stack.services), "service"))
        facts.append(f"{_compact(lines)} lines of code")
        svg.text(PAD, PAD + 50, "Architecture overview  ·  " + "  ·  ".join(facts), t.BODY, th.text_muted)

    def _draw_users(self, svg: Svg, layout: _Layout, clients: list[str]) -> None:
        th = self.theme
        first = layout.boxes[clients[0]]
        cx, top = first.cx, first.y - USERS_SPACE - self._lane_offset(layout)
        radius = 22
        svg.circle(cx, top + radius, radius, fill=th.surface_muted, stroke=th.border, stroke_width=1)
        t.icon(svg, "users", cx - 11, top + radius - 11, 22, th.text_muted)
        svg.text(cx + radius + 10, top + radius + 5, "Users", t.BODY, th.text_muted, weight=600)

        start = top + radius * 2 + 6
        if len(clients) == 1:
            self._arrow_line(svg, [(cx, start), (cx, first.y - 2)])
            return
        bus_x = first.x - 22
        svg.path(f"M {cx} {start} L {cx} {start + 12} L {bus_x + 10} {start + 12} "
                 f"Q {bus_x} {start + 12} {bus_x} {start + 22} L {bus_x} {layout.boxes[clients[-1]].cy - 10}",
                 fill="none", stroke=th.connector, stroke_width=1.5)
        for key in clients:
            box = layout.boxes[key]
            self._arrow_line(svg, [(bus_x, box.cy), (box.x - 2, box.cy)], draw_line=True)

    def _lane_offset(self, layout: _Layout) -> float:
        lanes = self._lane_edges(layout)
        return len(lanes) * LANE_STEP if lanes else 0

    def _draw_edges(self, svg: Svg, layout: _Layout, content_top: float) -> None:
        lanes = self._lane_edges(layout)
        lane_right = max((b.right for b in layout.boxes.values()), default=0)
        for edge in layout.edges:
            source, target = layout.boxes[edge.source], layout.boxes[edge.target]
            if edge in lanes:
                index = lanes.index(edge)
                lane_y = content_top - 26 - index * LANE_STEP
                side_x = lane_right + 22 + index * LANE_STEP
                self._lane(svg, source, target, lane_y, side_x, edge.label)
            else:
                siblings = [e for e in layout.edges if e.source == edge.source and e not in lanes
                            and layout.boxes[e.target].column == target.column]
                offset = (siblings.index(edge) - (len(siblings) - 1) / 2) * min(18, source.height / (len(siblings) + 1))
                self._curve(svg, source, target, edge.label, offset)

    def _curve(self, svg: Svg, source: _Box, target: _Box, label: str, offset: float = 0) -> None:
        th = self.theme
        x1, y1 = source.right + 2, source.cy + offset
        x2, y2 = target.x - 3, target.cy
        bend = (x2 - x1) * 0.5
        svg.path(f"M {x1:.1f} {y1:.1f} C {x1 + bend:.1f} {y1:.1f} {x2 - bend:.1f} {y2:.1f} {x2:.1f} {y2:.1f}",
                 fill="none", stroke=th.connector, stroke_width=1.5)
        _arrow_head(svg, x2 + 1, y2, 1, 0, th.connector)
        # The label sits on the curve, closer to the target where the curves have fanned out.
        u = 0.62
        lx = (1 - u) ** 3 * x1 + 3 * (1 - u) ** 2 * u * (x1 + bend) + 3 * (1 - u) * u ** 2 * (x2 - bend) + u ** 3 * x2
        ly = (1 - u) ** 3 * y1 + 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u ** 2 * y2 + u ** 3 * y2
        self._edge_label(svg, lx, ly, label)

    def _lane(self, svg: Svg, source: _Box, target: _Box, lane_y: float, side_x: float, label: str) -> None:
        th = self.theme
        start_x = source.right - 36
        r = 10
        path = (f"M {start_x} {source.y - 2} L {start_x} {lane_y + r} Q {start_x} {lane_y} {start_x + r} {lane_y} "
                f"L {side_x - r} {lane_y} Q {side_x} {lane_y} {side_x} {lane_y + r} "
                f"L {side_x} {target.cy - r} Q {side_x} {target.cy} {side_x - r} {target.cy} "
                f"L {target.right + 4} {target.cy}")
        svg.path(path, fill="none", stroke=th.connector, stroke_width=1.5, stroke_dasharray="5 4")
        _arrow_head(svg, target.right + 3, target.cy, -1, 0, th.connector)
        self._edge_label(svg, (start_x + side_x) / 2, lane_y, label)

    def _arrow_line(self, svg: Svg, points: list[tuple[float, float]], draw_line: bool = True) -> None:
        th = self.theme
        if draw_line:
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
            svg.path(d, fill="none", stroke=th.connector, stroke_width=1.5)
        (x1, y1), (x2, y2) = points[-2], points[-1]
        length = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
        _arrow_head(svg, x2, y2, (x2 - x1) / length, (y2 - y1) / length, th.connector)

    def _edge_label(self, svg: Svg, cx: float, cy: float, label: str) -> None:
        th = self.theme
        width = text_width(label, t.LABEL) + 16
        svg.rect(cx - width / 2, cy - 10, width, 20, 10, fill=th.background, stroke=th.border, stroke_width=1)
        svg.text(cx, cy + 4, label, t.LABEL, th.text_muted, anchor="middle")

    def _draw_app(self, svg: Svg, app: App, box: _Box) -> None:
        self._app_card(svg, app, box)

    def _app_card(self, svg: Svg | None, app: App, box: _Box) -> float:
        """Draw the card, or only measure it when `svg` is None. Returns its height."""
        th = self.theme
        accent = th.accent(app.kind)
        x, y, w = box.x, box.y, box.width
        inner = w - 32

        if svg is not None:
            svg.rect(x, y, w, box.height, 12, fill=th.surface, stroke=th.border, stroke_width=1)
            svg.rect(x + 16, y + 16, 40, 40, 10, fill=accent.soft)
            t.icon(svg, app.kind, x + 25, y + 25, 22, accent.strong)
            svg.text(x + 68, y + 31, KIND_LABELS.get(app.kind, "APP"), t.LABEL, accent.strong, weight=700,
                     letter_spacing=0.8)
            svg.text(x + 68, y + 51, fit_text(app.name, w - 84, t.HEADING, 700), t.HEADING, th.text, weight=700)

        # Technology chips, wrapped to the card width.
        chip_x, chip_y = x + 16, y + 70
        for tech in app.technologies:
            chip_w = text_width(tech, t.SMALL) + 18
            if chip_x + chip_w > x + 16 + inner and chip_x > x + 16:
                chip_x, chip_y = x + 16, chip_y + 30
            if svg is not None:
                svg.rect(chip_x, chip_y, chip_w, 24, 6, fill=th.surface_muted, stroke=th.border, stroke_width=1)
                svg.text(chip_x + 9, chip_y + 16.5, tech, t.SMALL, th.text)
            chip_x += chip_w + 6
        chips_bottom = chip_y + 24 if app.technologies else y + 62

        stats_y = chips_bottom + 24
        if svg is not None:
            svg.text(x + 16, stats_y, fit_text(self._app_stats(app), inner, t.SMALL), t.SMALL, th.text_muted)

        if not app.deployments:
            return stats_y + 18 - y
        separator = stats_y + 16
        if svg is not None:
            svg.line(x + 1, separator, x + w - 1, separator, stroke=th.border, stroke_width=1)
            t.icon(svg, "deploy", x + 16, separator + 11, 16, th.text_muted)
            svg.text(x + 40, separator + 24, fit_text(_deployment_text(app.deployments), inner - 26, t.SMALL),
                     t.SMALL, th.text_muted)
        return separator + 38 - y

    def _app_stats(self, app: App) -> str:
        parts = [_plural(app.files, "file"), f"{_compact(app.lines)} lines"]
        if self.endpoints[app.name]:
            parts.append(_plural(self.endpoints[app.name], "endpoint"))
        return "  ·  ".join(parts)

    def _draw_service(self, svg: Svg, service: Service, box: _Box) -> None:
        th = self.theme
        accent = th.accent(service.category)
        x, y, w = box.x, box.y, box.width
        svg.rect(x, y, w, box.height, 12, fill=th.surface, stroke=th.border, stroke_width=1)
        svg.rect(x + 14, y + 15, 40, 40, 10, fill=accent.soft)
        t.icon(svg, service.category, x + 23, y + 24, 22, accent.strong)
        svg.text(x + 66, y + 32, fit_text(service.name, w - 80, 15, 700), 15, th.text, weight=700)
        category = CATEGORY_LABELS.get(service.category, "Service")
        svg.text(x + 66, y + 51, fit_text(category, w - 80, t.SMALL), t.SMALL, th.text_muted)
        if service.details:
            details = "  ·  ".join(service.details)
            svg.text(x + 66, y + 70, fit_text(details, w - 80, t.SMALL), t.SMALL, accent.strong, weight=600)

    def _draw_footer(self, svg: Svg, width: float, height: float) -> None:
        th = self.theme
        y = height - PAD
        svg.line(PAD, y - 26, width - PAD, y - 26, stroke=th.border, stroke_width=1)
        if self.stack.ci:
            svg.text(PAD, y, "CI  ·  " + ", ".join(self.stack.ci), t.SMALL, th.text_muted)
        svg.text(width - PAD, y, "Generated with repo-xray", t.SMALL, th.text_subtle, anchor="end")

    def _description(self) -> str:
        apps = ", ".join(f"{a.name} ({KIND_LABELS.get(a.kind, 'app').lower()}, {', '.join(a.technologies[:2])})"
                         for a in self.stack.apps)
        services = ", ".join(s.name for s in self.stack.services) or "no external services"
        return f"{self.stack.name} is made of {apps}. It uses {services}."


def _arrow_head(svg: Svg, x: float, y: float, dx: float, dy: float, color: str) -> None:
    """Filled triangle with its tip at (x, y), pointing along (dx, dy)."""
    size, half = 8, 4.5
    bx, by = x - dx * size, y - dy * size
    svg.polygon([(x, y), (bx - dy * half, by + dx * half), (bx + dy * half, by - dx * half)], fill=color)


def _count(files: list[SourceFile], app: App, attribute: str) -> int:
    return sum(
        len(getattr(f, attribute)) for f in files
        if is_inside(f.path, app.path) and not is_test_path(f.path)
    )


def _deployment_text(deployments: list[str]) -> str:
    targets = [d for d in deployments if d != "Docker"]
    if not targets:
        return "Docker"
    text = " · ".join(targets)
    return f"{text}  (Docker)" if "Docker" in deployments else text


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _compact(number: int) -> str:
    return f"{number / 1000:.1f}k" if number >= 1000 else str(number)
