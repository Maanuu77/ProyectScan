import pytest

from repo_xray.analysis.linking import link_http_calls
from repo_xray.analysis.stack import App, Service, Stack
from repo_xray.render.overview import MAX_APPS, MAX_SERVICES, render_overview
from repo_xray.render.theme import DARK, LIGHT
from tests.conftest import analyse, write
from tests.svgcheck import SVG, box, by_id, ids, overflowing, parse, texts, texts_outside_their_card


def api(name: str) -> App:
    return App(name=name, path=name, kind="api", language="java", technologies=["Spring Boot 3.4"], files=3, lines=90)


def web(name: str) -> App:
    return App(name=name, path=name, kind="web", language="typescript", technologies=["Angular 19"], files=3, lines=90)


@pytest.mark.parametrize("theme", [LIGHT, DARK])
def test_full_stack_overview(shop, theme):
    stack, files = analyse(shop)

    svg = render_overview(stack, files, theme)

    root = parse(svg)
    assert root.attrib["role"] == "img"
    assert theme.background in svg
    labels = texts(svg)
    for expected in ["WHAT IS IT MADE OF?", "Users", "WEB APP", "web", "API", "api", "Angular 19", "Spring Boot 3.4",
                     "PostgreSQL", "PostGIS  ·  Cloud SQL", "Firebase Auth", "Redis",
                     "reads & writes", "signs in", "verifies users", "CI  ·  GitHub Actions"]:
        assert expected in labels, expected
    assert "Cloud Run  (Docker)" in labels


def test_description_summarises_the_stack(shop):
    stack, files = analyse(shop)

    description = parse(render_overview(stack, files, LIGHT)).find(f"{SVG}desc").text

    assert description.startswith(f"{stack.name} is made of api (API, Spring Boot 3.4, Java 21)")
    assert "PostgreSQL" in description


def test_each_tier_has_its_zone_and_data_is_told_apart_from_external_services(shop):
    stack, files = analyse(shop)

    svg = render_overview(stack, files, LIGHT)

    captions = {e.text: float(e.attrib["x"]) for e in parse(svg).iter(f"{SVG}text")
                if e.text in ("FRONTEND", "BACKEND", "DATA", "EXTERNAL SERVICES")}
    assert captions["FRONTEND"] < captions["BACKEND"] < captions["DATA"] == captions["EXTERNAL SERVICES"]
    data_y = box(by_id(svg, "service-postgresql"))[1], box(by_id(svg, "service-redis"))[1]
    external_y = box(by_id(svg, "service-firebase-auth"))[1], box(by_id(svg, "service-firebase-storage"))[1]
    assert max(data_y) < min(external_y)  # databases and caches above, what others run below


def test_cards_are_named_so_the_app_can_make_them_clickable(shop):
    stack, files = analyse(shop)

    found = ids(render_overview(stack, files, LIGHT))

    assert {"app-web", "app-api", "service-postgresql", "service-firebase-auth"} <= set(found)
    assert len(found) == len(set(found))  # an id names one element


def test_client_to_api_label_counts_http_calls(tmp_path):
    write(tmp_path, {
        "web/package.json": '{"dependencies": {"react": "^18.0.0"}}',
        "web/src/api.ts": "export const load = () => fetch('/api/items');\nexport const save = () => fetch('/api/items', {method: 'POST'});\n",
        "web/src/api.test.ts": "fetch('/api/ignored');\n",
        "api/pyproject.toml": '[project]\nname = "api"\ndependencies = ["fastapi"]\n',
        "api/main.py": "x = 1\n",
    })
    stack, files = analyse(tmp_path)

    assert "REST · 2 calls" in texts(render_overview(stack, files, LIGHT))


def test_with_several_backends_requests_are_counted_per_backend_or_not_at_all(tmp_path):
    controller = """\
        package {name};
        @RestController
        class {type}Controller {{ @GetMapping("/api/{name}") Object all() {{ return null; }} }}
    """
    pom = "<project><dependencies><dependency><artifactId>spring-boot-starter-web</artifactId></dependency></dependencies></project>"
    write(tmp_path, {
        "web/package.json": '{"dependencies": {"react": "^18.0.0"}}',
        "web/src/api.ts": "export const a = () => fetch('/api/orders');\nexport const b = () => fetch('/api/orders');\n"
                          "export const c = () => fetch('/api/billing');\nexport const d = () => fetch('/other');\n",
        "orders/pom.xml": pom,
        "orders/src/main/java/orders/OrdersController.java": controller.format(name="orders", type="Orders"),
        "billing/pom.xml": pom,
        "billing/src/main/java/billing/BillingController.java": controller.format(name="billing", type="Billing"),
    })
    stack, files = analyse(tmp_path)

    known = texts(render_overview(stack, files, LIGHT, links=link_http_calls(files)))
    unknown = texts(render_overview(stack, files, LIGHT))

    assert "REST · 2 calls" in known and "REST · 1 call" in known and "REST · 4 calls" not in known
    assert unknown.count("REST") == 2 and not any("calls" in label for label in unknown)  # no guessed numbers


def test_single_app_without_services_is_centred(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "tool"\n', "tool.py": "x = 1\n"})
    stack, files = analyse(tmp_path)

    svg = render_overview(stack, files, LIGHT)

    width = float(parse(svg).attrib["width"])
    assert width == 680
    assert "1 app  ·  1 line of code" in texts(svg)
    left, _, card_width, _ = box(by_id(svg, "app-tool"))
    assert left == pytest.approx(width - left - card_width)


def test_a_project_without_apps_still_draws(tmp_path):
    svg = render_overview(Stack(name="nothing-here"), [], LIGHT)

    assert "nothing-here" in texts(svg) and "Users" not in texts(svg)
    assert float(parse(svg).attrib["height"]) > 100


def test_long_names_never_overflow_their_card():
    name = "an-extremely-long-application-folder-name"
    stack = Stack(
        name="a-project-name-so-long-that-it-could-never-fit-on-one-line-of-any-reasonable-diagram",
        apps=[App(name=name, path="a", kind="api", language="java",
                  technologies=["Spring Boot 3.4", "A Technology With An Unreasonably Long Name 12.4"], files=1, lines=1)],
        services=[Service(name="A Very Long Managed Database Service Name", category="database", used_by=[name],
                          details=["With long details", "and even more details"])],
    )

    svg = render_overview(stack, [], LIGHT)

    assert overflowing(svg, margin=40) == []
    assert texts_outside_their_card(svg, "app-an-extremely-long-application-folder-name") == []
    assert texts_outside_their_card(svg, "service-a-very-long-managed-database-service-name") == []


def test_services_sit_next_to_the_apps_that_use_them():
    stack = Stack(name="demo", apps=[api("first"), api("second")], services=[
        Service("Alpha", "database", used_by=["second"]),
        Service("Omega", "database", used_by=["first"]),
    ])

    svg = render_overview(stack, [], LIGHT)

    assert box(by_id(svg, "app-first"))[1] < box(by_id(svg, "app-second"))[1]
    assert box(by_id(svg, "service-omega"))[1] < box(by_id(svg, "service-alpha"))[1]  # not alphabetical: no crossing


def test_too_many_services_are_summarised_by_name():
    services = [Service(f"Service {i:02}", "external", used_by=["api"] if i < 3 else []) for i in range(MAX_SERVICES + 4)]
    stack = Stack(name="demo", apps=[api("api")], services=services)

    svg = render_overview(stack, [], LIGHT)

    drawn = [i for i in ids(svg) if i.startswith("service-")]
    assert len(drawn) == MAX_SERVICES - 1
    assert {"service-service-00", "service-service-01", "service-service-02"} <= set(drawn)  # the used ones stay
    labels = texts(svg)
    assert "+ 5 more" in labels
    assert any("Service 11" in label for label in labels)  # nothing is silently left out


def test_too_many_apps_are_summarised_by_name():
    stack = Stack(name="demo", apps=[api(f"api-{i}") for i in range(MAX_APPS + 2)])

    svg = render_overview(stack, [], LIGHT)

    assert len([i for i in ids(svg) if i.startswith("app-")]) == MAX_APPS - 1
    assert "+ 3 more" in texts(svg)


def test_a_crowded_gap_keeps_the_colours_and_drops_the_words():
    names = [f"db{i}" for i in range(4)]
    crowded = Stack(name="demo", apps=[api("one"), api("two")],
                    services=[Service(n, "database", used_by=["one", "two"]) for n in names])
    calm = Stack(name="demo", apps=[api("one")], services=[Service(n, "database", used_by=["one"]) for n in names])

    assert "reads & writes" not in texts(render_overview(crowded, [], LIGHT))  # 8 connectors in one gap
    assert texts(render_overview(calm, [], LIGHT)).count("reads & writes") == 4


def test_frontends_that_reach_the_same_service_share_one_lane():
    stack = Stack(name="demo", apps=[web("site"), web("admin"), api("api")],
                  services=[Service("Firebase Auth", "auth", used_by=["site", "admin", "api"])])

    svg = render_overview(stack, [], LIGHT)

    assert texts(svg).count("signs in") == 1  # one lane, labelled once, for both frontends
    assert texts(svg).count("verifies users") == 1
    dashed = [e for e in parse(svg).iter(f"{SVG}path") if "stroke-dasharray" in e.attrib]
    assert len(dashed) == 2  # the shared path and the second frontend joining it


def test_labels_follow_the_language(shop):
    stack, files = analyse(shop)

    labels = texts(render_overview(stack, files, LIGHT, lang="es"))

    for expected in ["¿DE QUÉ ESTÁ HECHO?", "Usuarios", "APLICACIÓN WEB", "Base de datos", "lee y escribe",
                     "inicia sesión", "verifica usuarios", "DATOS", "SERVICIOS EXTERNOS", "Generado con repo-xray"]:
        assert expected in labels, expected
    assert any(label.startswith("2 aplicaciones  ·  ") for label in labels)
