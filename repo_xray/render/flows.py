"""Level 3 diagram: "What happens when…?"

Swimlanes, one per app plus one for data and services. Steps go down in
order, each in the lane of the app that runs it, so a request reads as a
staircase from the screen to the database. The step that crosses from
the frontend to the backend is labelled with the real HTTP route.
"""

from repo_xray import i18n
from repo_xray.analysis.flows import Flow, Step
from repo_xray.analysis.stack import Stack
from repo_xray.render import theme as t
from repo_xray.render.svg import Svg, fit_text, text_width

PAD = 40
LANE_WIDTH = 316
LANE_GAP = 36
CARD_HEIGHT = 58
ROW_GAP = 30
HEADER_HEIGHT = 132
LANE_HEADER = 56
SERVICE_LANE = ""  # key of the data lane; no app has an empty name


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

    def render(self) -> str:
        lanes = max(len(self.lanes), 1)
        width = max(PAD * 2 + lanes * LANE_WIDTH + (lanes - 1) * LANE_GAP, 720)
        offset = (width - (lanes * LANE_WIDTH + (lanes - 1) * LANE_GAP)) / 2
        rows_top = HEADER_HEIGHT + LANE_HEADER + 18
        heights = [self._card_height(step) for step in self.flow.steps]
        height = rows_top + sum(heights) + ROW_GAP * (len(heights) - 1) + 84
        svg = Svg(width, height, self.theme.background, title=i18n.text(self.lang, "flow.title", title=self.flow.title),
                  description=self._description())
        self._header(svg)
        lane_x = {lane: offset + i * (LANE_WIDTH + LANE_GAP) for i, lane in enumerate(self.lanes)}
        self._lanes(svg, lane_x, height)

        boxes, y = [], rows_top
        for step, card_height in zip(self.flow.steps, heights):
            boxes.append((lane_x[self._lane_of(step)] + 20, y, card_height))
            y += card_height + ROW_GAP
        for index in range(1, len(boxes)):
            label = f"{self.flow.method} {self.flow.route}" if index == self.flow.http_index else None
            self._connector(svg, boxes[index - 1], boxes[index], label)
        for index, (step, (x, y, card_height)) in enumerate(zip(self.flow.steps, boxes)):
            self._card(svg, step, index + 1, x, y, card_height)
        self._footer(svg, width, height)
        return svg.to_string()

    def _lane_of(self, step: Step) -> str:
        return SERVICE_LANE if step.layer == "service" else step.app or "code"

    # Drawing

    def _header(self, svg: Svg) -> None:
        th = self.theme
        svg.text(PAD, PAD + 18, i18n.text(self.lang, "flow.kicker"), t.LABEL, th.text_muted, weight=700, letter_spacing=1)
        svg.text(PAD, PAD + 48, fit_text(self.flow.title, 1000, 22, 700), 22, th.text, weight=700)
        svg.text(PAD, PAD + 72, f"{self.stack.name}  ·  {self.flow.method} {self.flow.route}", t.BODY,
                 th.text_muted)

    def _lanes(self, svg: Svg, lane_x: dict[str, float], height: float) -> None:
        th = self.theme
        top = HEADER_HEIGHT
        for lane, x in lane_x.items():
            app = self.apps.get(lane)
            kind = app.kind if app else "database"
            accent = th.accent(kind)
            svg.rect(x, top, LANE_WIDTH, height - top - 56, 14, fill=th.surface_muted, fill_opacity=0.6)
            svg.rect(x + 16, top + 14, 28, 28, 7, fill=accent.soft)
            t.icon(svg, kind, x + 21, top + 19, 18, accent.strong)
            name = lane if lane != SERVICE_LANE else i18n.text(self.lang, "flow.data_lane")
            svg.text(x + 54, top + 33, fit_text(name, LANE_WIDTH - 70, 15, 700), 15, th.text, weight=700)

    def _name_lines(self, step: Step) -> list[str]:
        """The step's name on one line, or split before the method when it is too long."""
        available = LANE_WIDTH - 40 - 60
        if step.layer == "service" or text_width(step.name, 14, 600) <= available:
            return [step.name]
        owner, dot, method = step.name.rpartition(".")
        if not dot:
            return [fit_text(step.name, available, 14, 600)]
        return [fit_text(owner, available, 14, 600), fit_text("." + method, available, 14, 600)]

    def _card_height(self, step: Step) -> float:
        return CARD_HEIGHT + 18 * (len(self._name_lines(step)) - 1)

    def _card(self, svg: Svg, step: Step, number: int, x: float, y: float, height: float) -> None:
        th = self.theme
        width = LANE_WIDTH - 40
        if step.layer == "service":  # always a single line, so it keeps CARD_HEIGHT
            category = self.categories.get(step.name, "database")
            accent = th.accent(category)
            svg.rect(x, y, width, CARD_HEIGHT, 10, fill=th.surface, stroke=accent.strong, stroke_width=1.5)
            svg.rect(x + 12, y + 11, 36, 36, 9, fill=accent.soft)
            t.icon(svg, category, x + 19, y + 18, 22, accent.strong)
            svg.text(x + 60, y + 25, i18n.text(self.lang, "flow.stores"), t.LABEL, accent.strong, weight=700, letter_spacing=0.6)
            svg.text(x + 60, y + 44, fit_text(step.name, width - 72, 15, 700), 15, th.text, weight=700)
            return
        accent = th.accent(t.LAYER_ACCENTS.get(step.layer, "neutral"))
        svg.rect(x, y, width, height, 10, fill=th.surface, stroke=th.border, stroke_width=1)
        svg.circle(x + 26, y + height / 2, 12, fill=accent.soft)
        svg.text(x + 26, y + height / 2 + 4.5, str(number), t.SMALL, accent.strong, weight=700, anchor="middle")
        key = f"step.{step.layer}"
        label = i18n.text(self.lang, key if key in i18n.TEXTS else "step.other")
        svg.text(x + 48, y + 24, label, t.LABEL, accent.strong, weight=700, letter_spacing=0.6)
        for index, line in enumerate(self._name_lines(step)):
            svg.text(x + 48, y + 43 + index * 18, line, 14, th.text, weight=600)

    def _connector(self, svg: Svg, start: tuple[float, float, float], end: tuple[float, float, float],
                   label: str | None) -> None:
        th = self.theme
        width = LANE_WIDTH - 40
        (x1, y1, h1), (x2, y2, _) = start, end
        colour = th.text_muted if label else th.connector
        stroke = 2 if label else 1.5
        if abs(x1 - x2) < 1:
            cx = x1 + width / 2
            svg.line(cx, y1 + h1 + 2, cx, y2 - 3, stroke=colour, stroke_width=stroke)
            _arrow_down(svg, cx, y2 - 1, colour)
            return
        # Leave the card on its side, run across, then drop into the next card from above.
        going_right = x2 > x1
        sx = x1 + width + 2 if going_right else x1 - 2
        sy = y1 + h1 / 2
        tx = x2 + width / 2
        r = 10
        bend = tx - r if going_right else tx + r
        svg.path(f"M {sx:.1f} {sy:.1f} L {bend:.1f} {sy:.1f} Q {tx:.1f} {sy:.1f} {tx:.1f} {sy + r:.1f} "
                 f"L {tx:.1f} {y2 - 3:.1f}", fill="none", stroke=colour, stroke_width=stroke)
        _arrow_down(svg, tx, y2 - 1, colour)
        if label:
            label_width = text_width(label, t.SMALL, 600) + 22
            lx = (sx + tx) / 2 if going_right else (sx + tx) / 2
            lx = max(lx, sx + label_width / 2 + 6) if going_right else lx
            svg.rect(lx - label_width / 2, sy - 30, label_width, 22, 11, fill=th.background,
                     stroke=th.border_strong, stroke_width=1)
            svg.text(lx, sy - 15, label, t.SMALL, th.text, weight=600, anchor="middle")

    def _footer(self, svg: Svg, width: float, height: float) -> None:
        th = self.theme
        svg.text(PAD, height - PAD + 8, i18n.text(self.lang, "flow.footer"),
                 t.SMALL, th.text_subtle)
        svg.text(width - PAD, height - PAD + 8, i18n.text(self.lang, "generated"), t.SMALL, th.text_subtle, anchor="end")

    def _description(self) -> str:
        steps = " -> ".join(step.name for step in self.flow.steps)
        return f"{self.flow.title} ({self.flow.method} {self.flow.route}): {steps}."


def _arrow_down(svg: Svg, x: float, y: float, colour: str) -> None:
    svg.polygon([(x, y), (x - 4.5, y - 8), (x + 4.5, y - 8)], fill=colour)
