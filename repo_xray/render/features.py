"""Level 2 diagram: "What does it do?"

One section per app, frontends first because that is what people see.
Each feature is a card with its description, a bar of the layers it
touches, and chips for what it uses. Backend features get their own
colour and frontend cards repeat it in their "Calls" chips, so the link
between both sides reads without a web of crossing lines.
"""

from repo_xray import i18n
from repo_xray.analysis.features import Feature, FeatureMap
from repo_xray.analysis.stack import App, Stack
from repo_xray.render import theme as t
from repo_xray.render.svg import Svg, fit_text, text_width, wrap_text

PAD = 40
COLUMNS = 3
CARD_WIDTH = 320
CARD_GAP = 20
MAX_CARDS = 9
WIDTH = PAD * 2 + COLUMNS * CARD_WIDTH + (COLUMNS - 1) * CARD_GAP
CLIENT_KINDS = ("web", "mobile", "desktop")
DRAWN_LAYERS = ("entry", "application", "domain", "data", "integration")


def render_features(stack: Stack, feature_map: FeatureMap, theme: t.Theme, lang: str = i18n.DEFAULT) -> str:
    return _FeatureRenderer(stack, feature_map, theme, lang).render()


class _FeatureRenderer:
    def __init__(self, stack: Stack, feature_map: FeatureMap, theme: t.Theme, lang: str):
        self.stack = stack
        self.map = feature_map
        self.theme = theme
        self.lang = lang
        palette = t.FEATURE_PALETTE[theme.name]
        apps = [a for a in stack.apps if feature_map.of_app(a.name)]
        self.apps = sorted(apps, key=lambda a: a.kind not in CLIENT_KINDS)
        backends = [a for a in self.apps if a.kind not in CLIENT_KINDS] or self.apps
        coloured = [f for a in backends for f in feature_map.of_app(a.name)]
        self.colour = {f.key: palette[i % len(palette)] for i, f in enumerate(coloured)}
        self.names = {f.key: f.name for f in feature_map.features}

    def render(self) -> str:
        sections = [(app, self._visible(app)) for app in self.apps]
        height = PAD + 80 + sum(self._section_height(app, features) for app, features in sections) + 70
        svg = Svg(WIDTH, height, self.theme.background,
                  title=f"{self.stack.name} features", description=self._description())
        self._header(svg)
        y = PAD + 80
        for app, features in sections:
            y = self._section(svg, app, features, y)
        self._legend(svg, height - PAD)
        return svg.to_string()

    def _visible(self, app: App) -> list[Feature]:
        features = sorted(self.map.of_app(app.name), key=lambda f: -len(f.files))
        return features if len(features) <= MAX_CARDS else features[: MAX_CARDS - 1]

    # Sections

    def _section_height(self, app: App, features: list[Feature]) -> float:
        rows = [features[i:i + COLUMNS] for i in range(0, len(features) + self._overflow(app), COLUMNS)]
        cards = sum(max((self._card(None, f, 0, 0) for f in row), default=96) for row in rows)
        return 56 + cards + CARD_GAP * max(len(rows) - 1, 0) + 46

    def _overflow(self, app: App) -> int:
        return 1 if len(self.map.of_app(app.name)) > MAX_CARDS else 0

    def _section(self, svg: Svg, app: App, features: list[Feature], y: float) -> float:
        th = self.theme
        accent = th.accent(app.kind)
        svg.rect(PAD, y, 32, 32, 8, fill=accent.soft)
        t.icon(svg, app.kind, PAD + 7, y + 7, 18, accent.strong)
        svg.text(PAD + 44, y + 22, app.name, t.HEADING, th.text, weight=700)
        total = len(self.map.of_app(app.name))
        detail = f"{i18n.text(self.lang, f'kind_title.{app.kind}')}  ·  {i18n.count(self.lang, total, 'feature')}"
        svg.text(PAD + 44 + text_width(app.name, t.HEADING, 700) + 12, y + 22, detail, t.BODY, th.text_muted)
        y += 56

        items: list[Feature | None] = [*features, *([None] * self._overflow(app))]
        for start in range(0, len(items), COLUMNS):
            row = items[start:start + COLUMNS]
            row_height = max(self._card(None, f, 0, 0) if f else 96 for f in row)
            for column, feature in enumerate(row):
                x = PAD + column * (CARD_WIDTH + CARD_GAP)
                if feature is None:
                    self._more_card(svg, app, x, y, row_height)
                else:
                    self._card(svg, feature, x, y, row_height)
            y += row_height + CARD_GAP
        y -= CARD_GAP

        shared = [s for s in self.map.shared if s.app == app.name]
        if shared:
            parts = sorted(shared, key=lambda s: -s.files)
            names = "  ·  ".join(f"{s.name} ({s.files})" for s in parts if not s.name.startswith("("))
            if names:
                svg.text(PAD, y + 26, fit_text(i18n.text(self.lang, "shared_code") + "  " + names, WIDTH - PAD * 2, t.SMALL),
                         t.SMALL, th.text_subtle)
        return y + 46

    # Cards

    def _card(self, svg: Svg | None, feature: Feature, x: float, y: float, height: float = 0) -> float:
        """Draw a feature card, or measure it when `svg` is None. Returns its natural height."""
        th = self.theme
        inner = CARD_WIDTH - 36
        colour = self.colour.get(feature.key)
        description = feature.description or ""
        lines = wrap_text(description, inner, t.BODY, max_lines=2)
        chips = self._chips(feature)

        if svg is not None:
            svg.rect(x, y, CARD_WIDTH, height, 12, fill=th.surface, stroke=th.border, stroke_width=1)
            if colour:
                svg.circle(x + 24, y + 27, 5, fill=colour)
            else:  # a frontend feature: it consumes coloured backend features, it has no colour of its own
                svg.circle(x + 24, y + 27, 4.25, fill="none", stroke=th.text_muted, stroke_width=1.5)
            stat = self._stat(feature)
            stat_width = text_width(stat, t.SMALL)
            svg.text(x + 38, y + 32, fit_text(feature.name, inner - stat_width - 20, 16, 700), 16, th.text,
                     weight=700)
            svg.text(x + CARD_WIDTH - 18, y + 32, stat, t.SMALL, th.text_muted, anchor="end")
            for index, line in enumerate(lines):
                svg.text(x + 18, y + 56 + index * 19, line, t.BODY, th.text_muted)

        bar_y = y + 56 + len(lines) * 19 + 2
        if svg is not None:
            self._layer_bar(svg, feature, x + 18, bar_y, inner)

        chip_y = bar_y + 22
        if not chips:
            return chip_y - y + 4
        if svg is not None:
            label = chips[0][2]
            svg.text(x + 18, chip_y + 16, label, t.LABEL, th.text_subtle, weight=600, letter_spacing=0.4)
        chip_x = x + 18 + text_width(chips[0][2], t.LABEL, 600) + 10
        start_x = chip_x
        for text, dot, _ in chips:
            width = text_width(text, t.SMALL) + (28 if dot else 18)
            if chip_x + width > x + 18 + inner and chip_x > start_x:
                chip_x, chip_y = start_x, chip_y + 30
            if svg is not None:
                svg.rect(chip_x, chip_y, width, 24, 12, fill=th.surface_muted, stroke=th.border, stroke_width=1)
                if dot:
                    svg.circle(chip_x + 13, chip_y + 12, 4, fill=dot)
                svg.text(chip_x + (23 if dot else 9), chip_y + 16.5, text, t.SMALL, th.text)
            chip_x += width + 6
        return chip_y + 24 + 18 - y

    def _chips(self, feature: Feature) -> list[tuple[str, str | None, str]]:
        """(text, dot colour, row label) for what the feature uses."""
        if feature.calls:
            targets = sorted(feature.calls, key=lambda k: -feature.calls[k])
            chips = [(self.names[k], self.colour.get(k), i18n.text(self.lang, "chip.calls")) for k in targets]
        elif feature.depends_on:
            targets = sorted(feature.depends_on, key=lambda k: -feature.depends_on[k])
            chips = [(self.names[k], self.colour.get(k), i18n.text(self.lang, "chip.uses")) for k in targets]
        else:
            chips = []
        label = chips[0][2] if chips else i18n.text(self.lang, "chip.uses")
        chips += [(service, None, label) for service in feature.services]
        return chips

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
            svg.rect(cursor, y, min(segment, x + width - cursor), 6, 3, fill=colour, fill_opacity=0.55)
            cursor += segment + gap

    def _more_card(self, svg: Svg, app: App, x: float, y: float, height: float) -> None:
        th = self.theme
        hidden = sorted(self.map.of_app(app.name), key=lambda f: -len(f.files))[MAX_CARDS - 1:]
        svg.rect(x, y, CARD_WIDTH, height, 12, fill=th.surface_muted, stroke=th.border, stroke_width=1,
                 stroke_dasharray="4 4")
        svg.text(x + 18, y + 32, i18n.text(self.lang, "more_features", n=len(hidden)), 16, th.text_muted, weight=700)
        names = ", ".join(f.name for f in hidden)
        for index, line in enumerate(wrap_text(names, CARD_WIDTH - 36, t.BODY, max_lines=3)):
            svg.text(x + 18, y + 56 + index * 19, line, t.BODY, th.text_subtle)

    def _stat(self, feature: Feature) -> str:
        if feature.endpoints:
            return i18n.count(self.lang, len(feature.endpoints), "endpoint")
        return i18n.count(self.lang, len(feature.files), "file")

    # Header and legend

    def _header(self, svg: Svg) -> None:
        th = self.theme
        svg.text(PAD, PAD + 24, self.stack.name, t.TITLE, th.text, weight=700)
        total = len(self.map.features)
        subtitle = f"{i18n.text(self.lang, 'features.subtitle')}  ·  {i18n.count(self.lang, total, 'feature')}"
        if len(self.apps) > 1:
            subtitle += " " + i18n.text(self.lang, "in_apps", n=len(self.apps))
        svg.text(PAD, PAD + 50, subtitle, t.BODY, th.text_muted)

    def _legend(self, svg: Svg, y: float) -> None:
        th = self.theme
        svg.line(PAD, y - 26, WIDTH - PAD, y - 26, stroke=th.border, stroke_width=1)
        x = PAD
        for layer in DRAWN_LAYERS:
            svg.rect(x, y - 9, 14, 6, 3, fill=th.accent(t.LAYER_ACCENTS[layer]).strong, fill_opacity=0.55)
            label = i18n.text(self.lang, f"layer.{layer}")
            svg.text(x + 20, y, label, t.SMALL, th.text_muted)
            x += 20 + text_width(label, t.SMALL) + 22
        svg.text(WIDTH - PAD, y, i18n.text(self.lang, "generated"), t.SMALL, th.text_subtle, anchor="end")

    def _description(self) -> str:
        parts = []
        for app in self.apps:
            names = ", ".join(f.name for f in self.map.of_app(app.name))
            parts.append(f"{app.name}: {names}")
        return i18n.text(self.lang, "features.description", name=self.stack.name) + " " + "; ".join(parts) + "."
