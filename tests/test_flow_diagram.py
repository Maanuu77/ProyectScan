import xml.etree.ElementTree as ElementTree

import pytest

from repo_xray.analysis.flows import Flow, Step
from repo_xray.analysis.stack import App, Service, Stack
from repo_xray.render.flows import render_flow
from repo_xray.render.svg import text_width
from repo_xray.render.theme import DARK, LIGHT

SVG = "{http://www.w3.org/2000/svg}"


def texts(svg: str) -> list[str]:
    return [element.text for element in ElementTree.fromstring(svg).iter(f"{SVG}text")]


def stack() -> Stack:
    return Stack(name="shop", apps=[App("web", "web", "web", "typescript"), App("api", "api", "api", "java")],
                 services=[Service("PostgreSQL", "database", used_by=["api"])])


def order_flow(name: str = "OrderController.create") -> Flow:
    return Flow(
        key="post-api-orders", title="Place an order", method="POST", route="/api/orders", feature="api/order",
        steps=[
            Step("w.CheckoutPage.buy", "CheckoutPage.buy", "web", "entry"),
            Step("w.OrdersApi.create", "OrdersApi.create", "web", "data"),
            Step("a.OrderController.create", name, "api", "entry"),
            Step("a.OrderService.place", "OrderService.place", "api", "application"),
            Step("PostgreSQL", "PostgreSQL", "PostgreSQL", "service"),
        ],
        http_index=2,
    )


@pytest.mark.parametrize("theme", [LIGHT, DARK])
def test_lanes_steps_and_route(theme):
    svg = render_flow(order_flow(), stack(), theme)

    labels = texts(svg)
    assert "Place an order" in labels
    assert "shop  ·  POST /api/orders" in labels
    for expected in ["web", "api", "Data & services", "CheckoutPage.buy", "OrderService.place", "PostgreSQL",
                     "ENTRY POINT", "DATA ACCESS", "APPLICATION LOGIC", "STORES THE RESULT", "1", "4"]:
        assert expected in labels, expected
    assert labels.count("POST /api/orders") == 1  # only the step that crosses to the backend is labelled


def test_lanes_follow_the_order_of_appearance_with_data_last():
    root = ElementTree.fromstring(render_flow(order_flow(), stack(), LIGHT))

    headers = [e for e in root.iter(f"{SVG}text") if e.attrib.get("font-size") == "15"]
    ordered = [e.text for e in sorted(headers, key=lambda e: float(e.attrib["x"]))]
    assert ordered[:3] == ["web", "api", "Data & services"]


def test_long_names_wrap_before_the_method_instead_of_being_cut():
    long_name = "ModerationController.keepReportedReview"

    labels = texts(render_flow(order_flow(long_name), stack(), LIGHT))

    assert "ModerationController" in labels
    assert ".keepReportedReview" in labels


def test_text_stays_inside_the_canvas():
    root = ElementTree.fromstring(render_flow(order_flow("X" * 80 + ".y"), stack(), LIGHT))

    width = float(root.attrib["width"])
    for element in root.iter(f"{SVG}text"):
        x = float(element.attrib["x"])
        anchor = element.attrib.get("text-anchor")
        size, weight = float(element.attrib["font-size"]), int(element.attrib.get("font-weight", 400))
        end = x if anchor == "end" else x + (text_width(element.text, size, weight) / (2 if anchor == "middle" else 1))
        assert end <= width, element.text
