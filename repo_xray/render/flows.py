"""Level 3 diagram: "What happens when…?"

Swimlanes, one zone per app plus one for data and services. Steps go down
in order, each in the lane of the app that runs it, so a request reads as
a staircase from the screen to the database. The HTTP request itself is
drawn where it crosses from one app to the next: its method, coloured by
what it does, and its real route. A flow that no screen in the project
starts still shows the request arriving at its first step.
"""

from repo_xray import i18n
from repo_xray.analysis.flows import Flow, Step
from repo_xray.analysis.stack import Stack
from repo_xray.render import components as c
from repo_xray.render import ids
from repo_xray.render import theme as t
from repo_xray.render.svg import Svg, fit_middle, fit_text, text_width

PAD = c.PAD
LANE_WIDTH = 340
LANE_GAP = 28
LANE_PAD = 20  # between a lane's border and its cards
LANE_HEADER = 62
CARD_WIDTH = LANE_WIDTH - LANE_PAD * 2
ROW_GAP = 28
REQUEST_ROW = 26 + ROW_GAP  # the request drawn above a flow that starts at the backend
MIN_WIDTH = 760
SERVICE_LANE = ""  # key of the data lane; no app has an empty name
STORAGE_CATEGORIES = ("database", "storage", "cache", "search")  # services that keep data

Box = tuple[float, float, float]  # x, y and height of a step's card


def render_flow(flow: Flow, stack: Stack, theme: t.Theme, lang: str = i18n.DEFAULT) -> str:
    return _FlowRenderer(flow, stack, theme, lang).render()


class _FlowRenderer:
    def __init__(self, flow: Flow, stack: Stack, theme: t.Theme, lang: str):
        self.flow = flow
        self.stack = stack
        self.theme = theme
        self.lang = lang
        self.apps = {a.name: a for a in stack.apps}
        self.categories = {s.name: s.category for s in stack.services}
        self.lanes: list[str] = []
        for step in flow.steps:
            lane = self._lane_of(step)
            if lane not in self.lanes:
                self.lanes.append(lane)
        if SERVICE_LANE in self.lanes:  # data always on the right
            self.lanes.remove(SERVICE_LANE)
            self.lanes.append(SERVICE_LANE)
        # The request crosses between two steps when a screen of the project starts the flow;
        # otherwise it arrives from outside, above the first step.
        self.arrives_from_outside = bool(flow.steps) and not flow.http_index

    def render(self) -> str:
        lanes = max(len(self.lanes), 1)
        lanes_width = lanes * LANE_WIDTH + (lanes - 1) * LANE_GAP
        width = max(PAD * 2 + lanes_width, MIN_WIDTH)
        offset = (width - lanes_width) / 2
        title = c.title_lines(self.flow.title, width, max_lines=2)
        lanes_top = c.header_bottom(len(title)) + 34
        rows_top = lanes_top + LANE_HEADER + (REQUEST_ROW if self.arrives_from_outside else 0)
        heights = [self._card_height(step) for step in self.flow.steps]
        rows_bottom = rows_top + sum(heights) + ROW_GAP * max(len(heights) - 1, 0)
        lanes_bottom = rows_bottom + LANE_PAD
        height = lanes_bottom + c.FOOTER_SPACE
        svg = Svg(width, height, self.theme.background, title=i18n.text(self.lang, "flow.title", title=self.flow.title),
                  description=self._description())
        self._header(svg, title, width)
        lane_x = {lane: offset + i * (LANE_WIDTH + LANE_GAP) for i, lane in enumerate(self.lanes)}
        self._lanes(svg, lane_x, lanes_top, lanes_bottom - lanes_top)

        boxes: list[Box] = []
        y = rows_top
        for step, card_height in zip(self.flow.steps, heights):
            boxes.append((lane_x[self._lane_of(step)] + LANE_PAD, y, card_height))
            y += card_height + ROW_GAP
        if self.arrives_from_outside:
            self._arriving_request(svg, boxes[0], rows_top - REQUEST_ROW)
        for index in range(1, len(boxes)):
            if index == self.flow.http_index:
                self._request(svg, boxes[index - 1], boxes[index])
            else:
                self._connector(svg, boxes[index - 1], boxes[index])
        for index, (step, (x, y, card_height)) in enumerate(zip(self.flow.steps, boxes)):
            self._card(svg, step, index + 1, x, y, card_height)
        c.footer(svg, self.theme, width, height, i18n.text(self.lang, "flow.footer"), i18n.text(self.lang, "generated"))
        return svg.to_string()

    def _lane_of(self, step: Step) -> str:
        return SERVICE_LANE if step.layer == "service" else step.app or "code"

    # Header and lanes

    def _header(self, svg: Svg, title: list[str], width: float) -> None:
        th = self.theme
        y = c.header(svg, th, 3, i18n.text(self.lang, "flow.kicker"), title)
        name = fit_text(self.stack.name, width * 0.4, t.BODY)
        svg.text(PAD, y, name, t.BODY, th.text_muted)
        x = PAD + text_width(name, t.BODY) + 12
        x += c.method_badge(svg, th, x, y - 13, self.flow.method) + 8
        svg.text(x, y, fit_middle(self.flow.route, width - PAD - x, t.SMALL, mono=True), t.SMALL, th.text_muted,
                 mono=True)

    def _lanes(self, svg: Svg, lane_x: dict[str, float], top: float, height: float) -> None:
        th = self.theme
        for lane, x in lane_x.items():
            app = self.apps.get(lane)
            kind = app.kind if app else "database" if lane == SERVICE_LANE else "library"
            c.zone(svg, th, x, top, LANE_WIDTH, height)
            c.icon_tile(svg, th, kind, x + LANE_PAD, top + 16, 30)
            name = lane if lane != SERVICE_LANE else i18n.text(self.lang, "flow.data_lane")
            caption = i18n.text(self.lang, f"kind_title.{app.kind}") if app else ""
            room = LANE_WIDTH - LANE_PAD * 2 - 42 - (text_width(caption, t.SMALL) + 12 if caption else 0)
            name = fit_text(name, room, t.SUBHEADING, 700)
            svg.text(x + LANE_PAD + 42, top + 36, name, t.SUBHEADING, th.text, weight=700)
            if caption:
                svg.text(x + LANE_PAD + 42 + text_width(name, t.SUBHEADING, 700) + 10, top + 36, caption, t.SMALL,
                         th.text_muted)

    # Steps

    def _parts(self, step: Step) -> tuple[str, str]:
        """(owner, member): `ResenaService.publicar` -> ("ResenaService", "publicar()")."""
        owner, dot, member = step.name.rpartition(".")
        return (owner, member + "()") if dot else ("", step.name + "()")

    def _card_height(self, step: Step) -> float:
        if step.layer == "service":
            return 62
        return 76 if self._parts(step)[0] else 58

    def _card(self, svg: Svg, step: Step, number: int, x: float, y: float, height: float) -> None:
        th = self.theme
        if step.layer == "service":
            category = self.categories.get(step.name, "database")
            accent = th.accent(category)
            c.card(svg, th, x, y, CARD_WIDTH, height, ids.service_id(step.name), stroke=accent.strong)
            c.icon_tile(svg, th, category, x + 13, y + 13, 36)
            svg.text(x + 61, y + 27, self._service_verb(category), t.LABEL, accent.strong, weight=700,
                     letter_spacing=0.6)
            svg.text(x + 61, y + 46, fit_text(step.name, CARD_WIDTH - 74, t.SUBHEADING, 700), t.SUBHEADING, th.text,
                     weight=700)
            return
        accent = th.accent(t.LAYER_ACCENTS.get(step.layer, "neutral"))
        c.card(svg, th, x, y, CARD_WIDTH, height, ids.step_id(number, step.feature))
        svg.circle(x + 26, y + height / 2, 12, fill=accent.soft)
        svg.text(x + 26, y + height / 2 + 4.5, str(number), t.SMALL, accent.strong, weight=700, anchor="middle")
        key = f"step.{step.layer}"
        label = i18n.text(self.lang, key if key in i18n.TEXTS else "step.other")
        svg.text(x + 50, y + 24, label, t.LABEL, accent.strong, weight=700, letter_spacing=0.6)
        owner, member = self._parts(step)
        room = CARD_WIDTH - 64
        if owner:  # the type on one line, what is called on it below, in code type
            svg.text(x + 50, y + 43, fit_middle(owner, room, 14, 600), 14, th.text, weight=600)
            svg.text(x + 50, y + 61, fit_middle(member, room, t.SMALL, mono=True), t.SMALL, th.text_muted, mono=True)
        else:
            svg.text(x + 50, y + 43, fit_middle(member, room, 13, mono=True), 13, th.text, mono=True)

    def _service_verb(self, category: str) -> str:
        """What the request does with the service where it ends, as far as its HTTP method tells."""
        if category not in STORAGE_CATEGORIES:
            return i18n.text(self.lang, "flow.calls_service")
        verbs = {"GET": "flow.reads", "DELETE": "flow.deletes"}
        return i18n.text(self.lang, verbs.get(self.flow.method, "flow.stores"))

    # Connectors

    def _connector(self, svg: Svg, start: Box, end: Box) -> None:
        th = self.theme
        (x1, y1, h1), (x2, y2, _) = start, end
        if abs(x1 - x2) < 1:
            cx = x1 + CARD_WIDTH / 2
            c.polyline(svg, [(cx, y1 + h1 + 2), (cx, y2 - 3)], th.connector)
            return
        # Leave the card on its side, run across, then drop into the next card from above.
        going_right = x2 > x1
        sx = x1 + CARD_WIDTH + 2 if going_right else x1 - 2
        tx = x2 + CARD_WIDTH / 2
        c.polyline(svg, [(sx, y1 + h1 / 2), (tx, y1 + h1 / 2), (tx, y2 - 3)], th.connector)

    def _request(self, svg: Svg, start: Box, end: Box) -> None:
        """The HTTP request between two apps: out of the caller, through the route, down into the handler."""
        th = self.theme
        (x1, y1, h1), (x2, y2, _) = start, end
        cy = y1 + h1 / 2
        width = c.route_width(self.flow.method, self.flow.route, LANE_WIDTH - 24)
        centre = x2 + CARD_WIDTH / 2
        left = centre - width / 2
        if x2 > x1:
            c.polyline(svg, [(x1 + CARD_WIDTH + 2, cy), (left - 3, cy)], th.text_muted, width=1.75)
        elif x2 < x1:
            c.polyline(svg, [(x1 - 2, cy), (left + width + 3, cy)], th.text_muted, width=1.75)
        else:  # caller and handler in the same lane: the request sits between them
            cy = (y1 + h1 + y2) / 2
            c.polyline(svg, [(centre, y1 + h1 + 2), (centre, cy - 13)], th.text_muted, width=1.75, arrow=False)
        c.polyline(svg, [(centre, cy + 13), (centre, y2 - 3)], th.text_muted, width=1.75)
        c.route_pill(svg, th, left, cy, self.flow.method, self.flow.route, LANE_WIDTH - 24)

    def _arriving_request(self, svg: Svg, first: Box, top: float) -> None:
        """No screen of the project sends this request: show it arriving at the first step."""
        th = self.theme
        x, y, _ = first
        width = c.route_width(self.flow.method, self.flow.route, LANE_WIDTH - 24)
        centre = x + CARD_WIDTH / 2
        c.polyline(svg, [(centre, top + 26), (centre, y - 3)], th.text_muted, width=1.75)
        c.route_pill(svg, th, centre - width / 2, top + 13, self.flow.method, self.flow.route, LANE_WIDTH - 24)

    def _description(self) -> str:
        steps = " -> ".join(step.name for step in self.flow.steps)
        return f"{self.flow.title} ({self.flow.method} {self.flow.route}): {steps}."
