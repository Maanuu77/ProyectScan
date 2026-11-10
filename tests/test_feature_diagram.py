import pytest

from repo_xray.analysis.features import Feature, FeatureMap, SharedPart
from repo_xray.analysis.stack import App, Stack
from repo_xray.render.features import CARD_WIDTH, MAX_CARDS, render_features
from repo_xray.render.theme import DARK, FEATURE_PALETTE, LIGHT
from tests.svgcheck import SVG, box, by_id, ids, overflowing, parse, texts, texts_outside_their_card


def shop() -> tuple[Stack, FeatureMap]:
    stack = Stack(name="shop", apps=[App("api", "api", "api", "java"), App("web", "web", "web", "typescript")])
    features = FeatureMap(
        features=[
            Feature("api/order", "Orders", "api", "api/order", files=["a", "b", "c"],
                    layers={"entry": 1, "application": 1, "data": 1}, description="Checkout and order history",
                    depends_on={"api/catalog": 2}),
            Feature("api/catalog", "Catalog", "api", "api/catalog", files=["d"], layers={"domain": 1}),
            Feature("web/checkout", "Checkout", "web", "web/checkout", files=["web/checkout/checkout-page.ts"],
                    layers={"entry": 1}, calls={"api/order": 3, "api/catalog": 1}, services=["Firebase Auth"],
                    description="Screen: Checkout. Calls Orders and Catalog.", screens=["Checkout"]),
        ],
        shared=[SharedPart("web", "core", 4), SharedPart("web", "(root)", 2)],
    )
    return stack, features


@pytest.mark.parametrize("theme", [LIGHT, DARK])
def test_zones_cards_and_chips(theme):
    svg = render_features(*shop(), theme)

    labels = texts(svg)
    assert labels.index("web") < labels.index("api")  # frontends first
    for expected in ["WHAT DOES IT DO?", "Orders", "Checkout and order history", "Catalog", "Checkout", "CALLS",
                     "USES", "Firebase Auth", "Shared code:  core (4)", "Data access", "3 features in 2 apps",
                     "1 screen"]:
        assert expected in labels, expected
    assert " ".join(labels).count("Screen: Checkout. Calls Orders and Catalog.") == 1  # wrapped, not cut


def test_each_app_is_a_zone_that_holds_its_cards():
    svg = render_features(*shop(), LIGHT)

    zones = [box(r) for r in parse(svg).iter(f"{SVG}rect") if r.attrib.get("stroke") == LIGHT.zone_border]
    assert len(zones) == 2
    for card_id, zone in (("feature-web-checkout", zones[0]), ("feature-api-order", zones[1])):
        x, y, width, height = box(by_id(svg, card_id))
        assert zone[0] < x and x + width < zone[0] + zone[2]
        assert zone[1] < y and y + height < zone[1] + zone[3]


def test_cards_are_named_after_their_feature():
    assert {"app-web", "app-api", "feature-api-order", "feature-api-catalog", "feature-web-checkout"} == set(
        ids(render_features(*shop(), LIGHT)))


def test_the_requests_that_cross_from_the_screens_to_the_api_are_counted_once():
    labels = texts(render_features(*shop(), LIGHT))

    assert labels.count("REST · 4 calls") == 1  # 3 to Orders and 1 to Catalog


def test_no_bridge_between_apps_that_do_not_call_each_other():
    stack, features = shop()
    features.features[2].calls = {}

    assert not any(label.startswith("REST") for label in texts(render_features(stack, features, LIGHT)))


def test_frontend_chips_reuse_the_backend_feature_colours():
    svg = render_features(*shop(), LIGHT)

    orders, catalog = FEATURE_PALETTE["light"][:2]
    circles = [c.attrib.get("fill") for c in parse(svg).iter(f"{SVG}circle")]
    assert circles.count(orders) == 2  # its card and the "Calls" chip in Checkout
    assert circles.count(catalog) == 3  # its card, the chip in Checkout and the "Uses" chip in Orders
    assert "none" in circles  # the frontend feature has no colour of its own


def test_overflowing_apps_get_a_more_card():
    stack = Stack(name="big", apps=[App("api", "api", "api", "java")])
    features = FeatureMap(features=[
        Feature(f"api/f{i}", f"Feature {i}", "api", f"api/f{i}", files=["x"] * (20 - i)) for i in range(12)
    ])

    labels = texts(render_features(stack, features, LIGHT))

    assert f"+ {12 - MAX_CARDS + 1} more features" in labels
    assert "Feature 0" in labels and "Feature 11" not in labels
    assert any("Feature 11" in label for label in labels)  # named inside the "more" card


def test_many_chips_stop_after_two_rows_and_say_how_many_are_left():
    stack, features = shop()
    others = [Feature(f"api/f{i}", f"Capability number {i}", "api", f"api/f{i}", files=["x"]) for i in range(9)]
    features.features += others
    features.features[2].calls = {f.key: 9 - i for i, f in enumerate(others)}

    svg = render_features(stack, features, LIGHT)

    labels = texts(svg)
    shown = [label for label in labels if label.startswith("Capability number")]
    hidden = next(label for label in labels if label.startswith("+") and label[1:].isdigit())
    card_chips = {label for label in shown if labels.count(label) == 2}  # in its own card and as a chip
    assert 0 < len(card_chips) < 9
    assert int(hidden[1:]) == 9 + 1 - len(card_chips)  # the rest, counting the service chip too
    assert texts_outside_their_card(svg, "feature-web-checkout") == []


def test_cards_in_a_row_share_their_height():
    stack, features = shop()
    features.features[0].description = "A description long enough to be wrapped over two lines of the card"

    svg = render_features(stack, features, LIGHT)

    orders, catalog = box(by_id(svg, "feature-api-order")), box(by_id(svg, "feature-api-catalog"))
    assert orders[1] == catalog[1] and orders[3] == catalog[3] and orders[2] == CARD_WIDTH


def test_text_stays_inside_the_canvas_and_its_card():
    stack, features = shop()
    features.features[0].description = "A description long enough to be wrapped over several lines " * 3
    features.features[0].name = "A feature name that is far too long to fit next to its number of endpoints"
    features.features[1].services = ["A service with a name that is wider than the whole card it is drawn in, really"]
    stack.apps[0].name = "an-application-with-a-name-that-is-much-longer-than-anyone-would-reasonably-choose-for-a-folder-in-a-repo"
    features.features[0].app = features.features[1].app = stack.apps[0].name

    svg = render_features(stack, features, LIGHT)

    assert overflowing(svg, margin=40) == []
    assert texts_outside_their_card(svg, "feature-api-order") == []
    assert texts_outside_their_card(svg, "feature-api-catalog") == []


def test_labels_follow_the_language():
    labels = texts(render_features(*shop(), LIGHT, lang="es"))

    for expected in ["¿QUÉ HACE?", "LLAMA A", "USA", "REST · 4 llamadas", "1 pantalla", "Acceso a datos"]:
        assert expected in labels, expected
