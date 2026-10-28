import xml.etree.ElementTree as ElementTree

import pytest

from repo_xray.analysis.features import Feature, FeatureMap, SharedPart
from repo_xray.analysis.stack import App, Stack
from repo_xray.render.features import MAX_CARDS, render_features
from repo_xray.render.svg import text_width
from repo_xray.render.theme import DARK, FEATURE_PALETTE, LIGHT

SVG = "{http://www.w3.org/2000/svg}"


def texts(svg: str) -> list[str]:
    return [element.text for element in ElementTree.fromstring(svg).iter(f"{SVG}text")]


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
                    description="Screen: Checkout. Calls Orders and Catalog."),
        ],
        shared=[SharedPart("web", "core", 4), SharedPart("web", "(root)", 2)],
    )
    return stack, features


@pytest.mark.parametrize("theme", [LIGHT, DARK])
def test_sections_cards_and_chips(theme):
    svg = render_features(*shop(), theme)

    labels = texts(svg)
    assert labels.index("web") < labels.index("api")  # frontends first
    for expected in ["Orders", "Checkout and order history", "Catalog", "Checkout", "CALLS", "USES",
                     "Firebase Auth", "Screen: Checkout. Calls Orders and Catalog.", "Shared code:  core (4)", "Data access"]:
        assert expected in labels, expected


def test_frontend_chips_reuse_the_backend_feature_colours():
    svg = render_features(*shop(), LIGHT)

    orders, catalog = FEATURE_PALETTE["light"][:2]
    circles = [c.attrib.get("fill") for c in ElementTree.fromstring(svg).iter(f"{SVG}circle")]
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


def test_text_stays_inside_the_canvas():
    stack, features = shop()
    features.features[0].description = "A description long enough to be wrapped over several lines " * 3

    root = ElementTree.fromstring(render_features(stack, features, LIGHT))

    width = float(root.attrib["width"])
    for element in root.iter(f"{SVG}text"):
        x = float(element.attrib["x"])
        end = x if element.attrib.get("text-anchor") == "end" else x + text_width(
            element.text, float(element.attrib["font-size"]), int(element.attrib.get("font-weight", 400)))
        assert end <= width - 18, element.text
