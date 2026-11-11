import pytest

from repo_xray.analysis.flows import Flow, Step
from repo_xray.analysis.stack import App, Service, Stack
from repo_xray.render.flows import render_flow
from repo_xray.render.theme import DARK, LIGHT
from tests.svgcheck import SVG, box, by_id, ids, overflowing, parse, texts, texts_outside_their_card


def stack() -> Stack:
    return Stack(name="shop", apps=[App("web", "web", "web", "typescript"), App("api", "api", "api", "java")],
                 services=[Service("PostgreSQL", "database", used_by=["api"]),
                           Service("Firebase Auth", "auth", used_by=["api"])])


def order_flow(name: str = "OrderController.create", method: str = "POST", service: str = "PostgreSQL") -> Flow:
    return Flow(
        key="post-api-orders", title="Place an order", method=method, route="/api/orders", feature="api/order",
        steps=[
            Step("w.CheckoutPage.buy", "CheckoutPage.buy", "web", "entry", "web/checkout"),
            Step("w.OrdersApi.create", "OrdersApi.create", "web", "data"),
            Step("a.OrderController.create", name, "api", "entry", "api/order"),
            Step("a.OrderService.place", "OrderService.place", "api", "application", "api/order"),
            Step(service, service, service, "service"),
        ],
        http_index=2,
    )


def backend_flow() -> Flow:
    flow = order_flow()
    flow.steps, flow.http_index = flow.steps[2:], None
    return flow


@pytest.mark.parametrize("theme", [LIGHT, DARK])
def test_lanes_steps_and_route(theme):
    svg = render_flow(order_flow(), stack(), theme)

    labels = texts(svg)
    for expected in ["WHAT HAPPENS WHEN…", "Place an order", "shop", "web", "api", "Data & services", "CheckoutPage",
                     "buy()", "OrderService", "place()", "PostgreSQL", "ENTRY POINT", "DATA ACCESS",
                     "APPLICATION LOGIC", "STORES THE RESULT", "1", "4"]:
        assert expected in labels, expected
    assert labels.count("/api/orders") == 2  # under the title, and where the request crosses to the backend
    assert labels.count("POST") == 2


def test_lanes_follow_the_order_of_appearance_with_data_last():
    root = parse(render_flow(order_flow(), stack(), LIGHT))

    headers = [e for e in root.iter(f"{SVG}text") if e.text in ("web", "api", "Data & services")]
    assert [e.text for e in sorted(headers, key=lambda e: float(e.attrib["x"]))] == ["web", "api", "Data & services"]


def test_a_step_shows_its_type_and_what_is_called_on_it():
    svg = render_flow(order_flow("ModerationController.keepReportedReview"), stack(), LIGHT)

    owner = next(e for e in parse(svg).iter(f"{SVG}text") if e.text == "ModerationController")
    member = next(e for e in parse(svg).iter(f"{SVG}text") if e.text == "keepReportedReview()")
    assert float(owner.attrib["y"]) < float(member.attrib["y"])
    assert "font-family" in member.attrib and "font-family" not in owner.attrib  # code type for the call


def test_a_function_without_an_owner_is_a_single_line():
    flow = order_flow()
    flow.steps[1] = Step("w.api.createOrder", "createOrder", "web", "data")

    svg = render_flow(flow, stack(), LIGHT)

    assert "createOrder()" in texts(svg)
    assert box(by_id(svg, "step-2-"))[3] < box(by_id(svg, "step-1-web-checkout"))[3]


def test_the_request_is_drawn_between_the_caller_and_the_handler():
    svg = render_flow(order_flow(), stack(), LIGHT)

    route = [e for e in parse(svg).iter(f"{SVG}text") if e.text == "/api/orders"][-1]
    caller, handler = box(by_id(svg, "step-2-")), box(by_id(svg, "step-3-api-order"))
    assert float(route.attrib["x"]) > caller[0] + caller[2]  # to the right of the caller, in the backend's lane
    assert caller[1] < float(route.attrib["y"]) < handler[1]  # level with the caller, above the handler


def test_a_flow_no_screen_starts_shows_the_request_arriving():
    svg = render_flow(backend_flow(), stack(), LIGHT)

    labels = texts(svg)
    assert "web" not in labels  # no frontend lane
    assert labels.count("/api/orders") == 2 and labels.count("POST") == 2
    route = [e for e in parse(svg).iter(f"{SVG}text") if e.text == "/api/orders"][-1]
    assert float(route.attrib["y"]) < box(by_id(svg, "step-1-api-order"))[1]  # above the first step


@pytest.mark.parametrize("method, service, verb", [
    ("POST", "PostgreSQL", "STORES THE RESULT"),
    ("PUT", "PostgreSQL", "STORES THE RESULT"),
    ("GET", "PostgreSQL", "READS THE DATA"),
    ("DELETE", "PostgreSQL", "DELETES THE DATA"),
    ("POST", "Firebase Auth", "CALLS THE SERVICE"),
    ("GET", "Firebase Auth", "CALLS THE SERVICE"),
])
def test_the_last_card_says_what_the_request_does_there(method, service, verb):
    labels = texts(render_flow(order_flow(method=method, service=service), stack(), LIGHT))

    assert verb in labels
    assert sum(label in ("STORES THE RESULT", "READS THE DATA", "DELETES THE DATA", "CALLS THE SERVICE")
               for label in labels) == 1


def test_steps_are_named_after_their_feature_and_the_service_after_itself():
    found = ids(render_flow(order_flow(), stack(), LIGHT))

    assert found == ["step-1-web-checkout", "step-2-", "step-3-api-order", "step-4-api-order", "service-postgresql"]


def test_a_long_title_wraps_instead_of_leaving_the_canvas():
    flow = order_flow()
    flow.title = "Keep a reported review, clear every report filed against it and notify the people who reported it"

    svg = render_flow(flow, stack(), LIGHT)

    title = [e for e in parse(svg).iter(f"{SVG}text") if e.attrib["font-size"] == "26"]
    assert len(title) == 2 and title[0].text.startswith("Keep a reported review")
    assert overflowing(svg, margin=40) == []


def test_text_stays_inside_the_canvas_and_its_card():
    flow = order_flow("X" * 80 + "." + "y" * 80)
    flow.route = "/api/v1/" + "/".join(f"segment{i}" for i in range(20)) + "/{id}/end"
    wide = Stack(name="a-project-with-a-long-name-" * 4, apps=stack().apps, services=stack().services)

    svg = render_flow(flow, wide, LIGHT)

    assert overflowing(svg, margin=40) == []
    assert texts_outside_their_card(svg, "step-3-api-order") == []
    routes = [label for label in texts(svg) if label.startswith("/api/v1/") and label.endswith("/{id}/end")]
    assert len(routes) == 2 and all("…" in label for label in routes)  # shortened in the middle: both ends stay


def test_labels_follow_the_language():
    labels = texts(render_flow(order_flow(method="GET"), stack(), LIGHT, lang="es"))

    for expected in ["QUÉ PASA CUANDO…", "PUNTO DE ENTRADA", "LEE LOS DATOS", "Datos y servicios"]:
        assert expected in labels, expected
