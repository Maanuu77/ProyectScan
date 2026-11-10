"""Level 2 diagram: "What does it do?"

One zone per app, frontends first because that is what people see. Each
feature is a card with its description, a bar of the layers it touches,
and chips for what it uses. Backend features get their own colour and
frontend cards repeat it in their "Calls" chips, so the link between both
sides reads without a web of crossing lines; one connector between the
zones says how many requests cross from the screens to the API.
"""

from repo_xray import i18n
from repo_xray.analysis.features import Feature, FeatureMap
from repo_xray.analysis.stack import App, Stack
from repo_xray.render import components as c
from repo_xray.render import ids
from repo_xray.render import theme as t
from repo_xray.render.requests import CLIENT_KINDS
from repo_xray.render.svg import Svg, fit_text, text_width, wrap_text

PAD = c.PAD
ZONE_PAD = 20
ZONE_HEADER = 70  # the app's icon, name and totals above its cards
ZONE_GAP = 20
BRIDGE = 60  # room between two zones when a connector crosses from one to the other
COLUMNS = 3
CARD_WIDTH = 316
CARD_GAP = 16
MAX_CARDS = 9
MAX_CHIP_ROWS = 2
WIDTH = PAD * 2 + ZONE_PAD * 2 + COLUMNS * CARD_WIDTH + (COLUMNS - 1) * CARD_GAP
DRAWN_LAYERS = ("entry", "application", "domain", "data", "integration")

Chip = tuple[str, str | None]  # (text, dot colour)


def render_features(stack: Stack, feature_map: FeatureMap, theme: t.Theme, lang: str = i18n.DEFAULT,
                    requests: int | None = None) -> str:
    """Draw the feature map. `requests` is how many HTTP requests cross from the frontends to the
    backends, as the overview counts them; without it, the calls between features are added up."""
    return _FeatureRenderer(stack, feature_map, theme, lang, requests).render()


class _FeatureRenderer:
    def __init__(self, stack: Stack, feature_map: FeatureMap, theme: t.Theme, lang: str,
                 requests: int | None = None):
        self.stack = stack
        self.map = feature_map
        self.theme = theme
        self.lang = lang
        self.requests = requests
        palette = t.FEATURE_PALETTE[theme.name]
        apps = [a for a in stack.apps if feature_map.of_app(a.name)]
        self.apps = sorted(apps, key=lambda a: a.kind not in CLIENT_KINDS)
        backends = [a for a in self.apps if a.kind not in CLIENT_KINDS] or self.apps
        coloured = [f for a in backends for f in feature_map.of_app(a.name)]
        self.colour = {f.key: palette[i % len(palette)] for i, f in enumerate(coloured)}
        self.names = {f.key: f.name for f in feature_map.features}

    def render(self) -> str:
        sections = [(app, self._visible(app)) for app in self.apps]
        gaps = [self._gap_after(index) for index in range(len(sections))]
        top = c.header_bottom() + 34
        height = top + sum(self._zone_height(app, features) for app, features in sections) + sum(gaps) + c.FOOTER_SPACE
        svg = Svg(WIDTH, height, self.theme.background,
                  title=f"{self.stack.name} features", description=self._description())
        self._header(svg)
        y = top
        for index, (app, features) in enumerate(sections):
            bottom = self._zone(svg, app, features, y)
            if gaps[index] == BRIDGE:
                self._bridge(svg, bottom)
            y = bottom + gaps[index]
        legend = [(self.theme.accent(t.LAYER_ACCENTS[layer]).strong, i18n.text(self.lang, f"layer.{layer}"))
                  for layer in DRAWN_LAYERS]
        c.footer(svg, self.theme, WIDTH, height, None, i18n.text(self.lang, "generated"), legend)
        return svg.to_string()

    def _visible(self, app: App) -> list[Feature]:
        features = sorted(self.map.of_app(app.name), key=lambda f: -len(f.files))
        return features if len(features) <= MAX_CARDS else features[: MAX_CARDS - 1]

    def _overflow(self, app: App) -> int:
        return 1 if len(self.map.of_app(app.name)) > MAX_CARDS else 0

    def _is_client(self, app: App) -> bool:
        return app.kind in CLIENT_KINDS

    def _requests(self) -> int:
        """HTTP requests that cross from the client apps to the others."""
        if self.requests is not None:
            return self.requests
        clients = {a.name for a in self.apps if self._is_client(a)}
        return sum(sum(f.calls.values()) for f in self.map.features if f.app in clients)

    def _gap_after(self, index: int) -> float:
        if index == len(self.apps) - 1:
            return 0
        crossing = self._is_client(self.apps[index]) and not self._is_client(self.apps[index + 1])
        return BRIDGE if crossing and self._requests() else ZONE_GAP

    # Zones

    def _rows(self, app: App, features: list[Feature]) -> list[list[Feature | None]]:
        items: list[Feature | None] = [*features, *([None] * self._overflow(app))]
        return [items[i:i + COLUMNS] for i in range(0, len(items), COLUMNS)]

    def _row_height(self, row: list[Feature | None]) -> float:
        return max(max((self._card(None, f, 0, 0) for f in row if f), default=0), 104 if None in row else 0)

    def _shared(self, app: App) -> str:
        parts = sorted((s for s in self.map.shared if s.app == app.name), key=lambda s: -s.files)
        names = "  ·  ".join(f"{s.name} ({s.files})" for s in parts if not s.name.startswith("("))
        return f"{i18n.text(self.lang, 'shared_code')}  {names}" if names else ""

    def _zone_height(self, app: App, features: list[Feature]) -> float:
        rows = self._rows(app, features)
        cards = sum(self._row_height(row) for row in rows) + CARD_GAP * max(len(rows) - 1, 0)
        return ZONE_HEADER + cards + (34 if self._shared(app) else 0) + ZONE_PAD

    def _zone(self, svg: Svg, app: App, features: list[Feature], y: float) -> float:
        """Draw one app with its features. Returns the zone's bottom."""
        th = self.theme
        x, width = PAD, WIDTH - PAD * 2
        height = self._zone_height(app, features)
        c.zone(svg, th, x, y, width, height)
        svg.rect(x + ZONE_PAD, y + 18, 34, 34, 9, fill=th.accent(app.kind).soft, id=ids.app_id(app.name))
        t.icon(svg, app.kind, x + ZONE_PAD + 8, y + 26, 18, th.accent(app.kind).strong)
        totals = self._totals(app)
        totals_width = sum(c.stat_width(value, label) + 18 for value, label in totals)
        name = fit_text(app.name, width - ZONE_PAD * 2 - 46 - totals_width - 180, t.HEADING, 700)
        svg.text(x + ZONE_PAD + 46, y + 41, name, t.HEADING, th.text, weight=700)
        kind = i18n.text(self.lang, f"kind_title.{app.kind}")
        svg.text(x + ZONE_PAD + 46 + text_width(name, t.HEADING, 700) + 12, y + 41, kind, t.BODY, th.text_muted)
        stat_x = x + width - ZONE_PAD - totals_width + 18
        for value, label in totals:
            stat_x += c.stat(svg, th, stat_x, y + 41, value, label) + 18

        card_y = y + ZONE_HEADER
        for row in self._rows(app, features):
            row_height = self._row_height(row)
            for column, feature in enumerate(row):
                card_x = x + ZONE_PAD + column * (CARD_WIDTH + CARD_GAP)
                if feature is None:
                    self._more_card(svg, app, card_x, card_y, row_height)
                else:
                    self._card(svg, feature, card_x, card_y, row_height)
            card_y += row_height + CARD_GAP
        shared = self._shared(app)
        if shared:
            svg.text(x + ZONE_PAD + 2, card_y - CARD_GAP + 26, fit_text(shared, width - ZONE_PAD * 2 - 4, t.SMALL),
                     t.SMALL, th.text_subtle)
        return y + height

    def _totals(self, app: App) -> list[tuple[str, str]]:
        """What the app adds up to, on the right of its header: features, then screens or endpoints."""
        features = self.map.of_app(app.name)
        counted = [i18n.count(self.lang, len(features), "feature")]
        screens = sum(len(f.screens) for f in features)
        endpoints = sum(len(f.endpoints) for f in features)
        if endpoints:
            counted.append(i18n.count(self.lang, endpoints, "endpoint"))
        elif screens and self._is_client(app):
            counted.append(i18n.count(self.lang, screens, "screen"))
        return [(value, label) for value, _, label in (text.partition(" ") for text in counted)]

    def _bridge(self, svg: Svg, y: float) -> None:
        """The requests that cross from the screens above to the API below."""
        th = self.theme
        cx = WIDTH / 2
        c.polyline(svg, [(cx, y + 5), (cx, y + BRIDGE - 3)], th.text_muted, width=1.75)
        c.pill(svg, th, cx, y + BRIDGE / 2 - 2, f"REST · {i18n.count(self.lang, self._requests(), 'call')}",
               colour=th.text, border=th.border_strong, weight=600)

    # Cards

    def _card(self, svg: Svg | None, feature: Feature, x: float, y: float, height: float = 0) -> float:
        """Draw a feature card, or measure it when `svg` is None. Returns its natural height."""
        th = self.theme
        inner = CARD_WIDTH - 36
        colour = self.colour.get(feature.key)
        lines = wrap_text(feature.description or "", inner, t.BODY, max_lines=2)

        if svg is not None:
            c.card(svg, th, x, y, CARD_WIDTH, height, ids.feature_id(feature.key))
            if colour:
                svg.circle(x + 23, y + 26, 5, fill=colour)
            else:  # a frontend feature: it consumes coloured backend features, it has no colour of its own
                svg.circle(x + 23, y + 26, 4.25, fill="none", stroke=th.text_muted, stroke_width=1.5)
            stat = self._stat(feature)
            stat_width = text_width(stat, t.SMALL)
            svg.text(x + 36, y + 31, fit_text(feature.name, inner - stat_width - 30, t.SUBHEADING, 700),
                     t.SUBHEADING, th.text, weight=700)
            svg.text(x + CARD_WIDTH - 18, y + 31, stat, t.SMALL, th.text_muted, anchor="end")
            for index, line in enumerate(lines):
                svg.text(x + 18, y + 55 + index * 19, line, t.BODY, th.text_muted)

        bar_y = y + 44 + len(lines) * 19 + 6
        if svg is not None:
            self._layer_bar(svg, feature, x + 18, bar_y, inner)

        label, chips = self._chips(feature)
        if not chips:
            return bar_y + 6 + 18 - y
        chip_y = bar_y + 20
        label_width = text_width(label, t.LABEL, 600) + 10
        placed = self._place_chips(chips, inner - label_width)
        if svg is not None:
            svg.text(x + 18, chip_y + 16, label, t.LABEL, th.text_subtle, weight=600, letter_spacing=0.4)
            for (text, dot), chip_x, row in placed:
                c.chip(svg, th, x + 18 + label_width + chip_x, chip_y + row * (c.CHIP_HEIGHT + c.CHIP_GAP), text, dot,
                       radius=12)
        rows = placed[-1][2] + 1
        return chip_y + rows * c.CHIP_HEIGHT + (rows - 1) * c.CHIP_GAP + 16 - y

    def _chips(self, feature: Feature) -> tuple[str, list[Chip]]:
        """The row's label and its chips: the features it calls or uses, then the services it reaches."""
        related = feature.calls or feature.depends_on
        label = i18n.text(self.lang, "chip.calls" if feature.calls else "chip.uses")
        chips: list[Chip] = [(self.names[k], self.colour.get(k)) for k in sorted(related, key=lambda k: -related[k])]
        return label, chips + [(service, None) for service in feature.services]

    def _place_chips(self, chips: list[Chip], width: float) -> list[tuple[Chip, float, int]]:
        """Lay chips out in rows of `width`: (chip, x, row). Past the last row, "+N" stands for the rest."""

        def fitted(chip: Chip) -> Chip:
            room = width - (28 if chip[1] else 18)
            return fit_text(chip[0], room, t.SMALL), chip[1]

        placed: list[tuple[Chip, float, int]] = []
        x, row = 0.0, 0
        for index, chip in enumerate(chips):
            chip = fitted(chip)
            needed = c.chip_width(chip[0], dot=bool(chip[1]))
            if x + needed > width and x > 0:
                x, row = 0.0, row + 1
            if row == MAX_CHIP_ROWS:
                more: Chip = (f"+{len(chips) - index}", None)
                while placed and placed[-1][2] == row - 1 and (
                        placed[-1][1] + c.chip_width(placed[-1][0][0], dot=bool(placed[-1][0][1])) + c.CHIP_GAP
                        + c.chip_width(more[0]) > width):
                    placed.pop()  # make room for the "+N" chip on the last row
                    more = (f"+{len(chips) - len(placed)}", None)
                last = placed[-1] if placed and placed[-1][2] == row - 1 else None
                start = last[1] + c.chip_width(last[0][0], dot=bool(last[0][1])) + c.CHIP_GAP if last else 0.0
                placed.append((more, start, row - 1))
                break
            placed.append((chip, x, row))
            x += needed + c.CHIP_GAP
        return placed

    def _layer_bar(self, svg: Svg, feature: Feature, x: float, y: float, width: float) -> None:
        th = self.theme
        counts = [(layer, feature.layers.get(layer, 0)) for layer in DRAWN_LAYERS]
        total = sum(count for _, count in counts)
        svg.rect(x, y, width, 6, 3, fill=th.surface_muted)
        if not total:
            return
        cursor = x
        gap = 2
        drawn = [(layer, count) for layer, count in counts if count]
        usable = width - gap * (len(drawn) - 1)
        for layer, count in drawn:
            segment = max(usable * count / total, 6)
            colour = th.accent(t.LAYER_ACCENTS[layer]).strong
            svg.rect(cursor, y, max(min(segment, x + width - cursor), 0), 6, 3, fill=colour, fill_opacity=0.6)
            cursor += segment + gap

    def _more_card(self, svg: Svg, app: App, x: float, y: float, height: float) -> None:
        th = self.theme
        hidden = sorted(self.map.of_app(app.name), key=lambda f: -len(f.files))[MAX_CARDS - 1:]
        c.card(svg, th, x, y, CARD_WIDTH, height, dashed=True, muted=True)
        svg.text(x + 18, y + 31, i18n.text(self.lang, "more_features", n=len(hidden)), t.SUBHEADING, th.text_muted,
                 weight=700)
        names = ", ".join(f.name for f in hidden)
        for index, line in enumerate(wrap_text(names, CARD_WIDTH - 36, t.BODY, max_lines=3)):
            svg.text(x + 18, y + 55 + index * 19, line, t.BODY, th.text_subtle)

    def _stat(self, feature: Feature) -> str:
        if feature.endpoints:
            return i18n.count(self.lang, len(feature.endpoints), "endpoint")
        if feature.screens:
            return i18n.count(self.lang, len(feature.screens), "screen")
        return i18n.count(self.lang, len(feature.files), "file")

    # Header

    def _header(self, svg: Svg) -> None:
        th = self.theme
        y = c.header(svg, th, 2, i18n.text(self.lang, "kicker.features"), c.title_lines(self.stack.name, WIDTH))
        total = len(self.map.features)
        subtitle = i18n.count(self.lang, total, "feature")
        if len(self.apps) > 1:
            subtitle += " " + i18n.text(self.lang, "in_apps", n=len(self.apps))
        svg.text(PAD, y, subtitle, t.BODY, th.text_muted)

    def _description(self) -> str:
        parts = []
        for app in self.apps:
            names = ", ".join(f.name for f in self.map.of_app(app.name))
            parts.append(f"{app.name}: {names}")
        return i18n.text(self.lang, "features.description", name=self.stack.name) + " " + "; ".join(parts) + "."
