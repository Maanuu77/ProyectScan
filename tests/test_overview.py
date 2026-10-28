import xml.etree.ElementTree as ElementTree

import pytest

from repo_xray.analysis.stack import App, Service, Stack
from repo_xray.render.overview import render_overview
from repo_xray.render.svg import text_width
from repo_xray.render.theme import DARK, LIGHT
from tests.conftest import analyse, write

SVG = "{http://www.w3.org/2000/svg}"


def texts(svg: str) -> list[str]:
    return [element.text for element in ElementTree.fromstring(svg).iter(f"{SVG}text")]


@pytest.mark.parametrize("theme", [LIGHT, DARK])
def test_full_stack_overview(shop, theme):
    stack, files = analyse(shop)

    svg = render_overview(stack, files, theme)

    root = ElementTree.fromstring(svg)
    assert root.attrib["role"] == "img"
    assert theme.background in svg
    labels = texts(svg)
    for expected in ["Users", "WEB APP", "web", "API", "api", "Angular 19", "Spring Boot 3.4",
                     "PostgreSQL", "PostGIS  ·  Cloud SQL", "Firebase Auth", "Redis",
                     "reads & writes", "signs in", "verifies users", "CI  ·  GitHub Actions"]:
        assert expected in labels, expected
    assert "Cloud Run  (Docker)" in labels


def test_description_summarises_the_stack(shop):
    stack, files = analyse(shop)

    description = ElementTree.fromstring(render_overview(stack, files, LIGHT)).find(f"{SVG}desc").text

    assert description.startswith(f"{stack.name} is made of api (API, Spring Boot 3.4, Java 21)")
    assert "PostgreSQL" in description


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


def test_single_app_without_services_is_centred(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "tool"\n', "tool.py": "x = 1\n"})
    stack, files = analyse(tmp_path)

    svg = render_overview(stack, files, LIGHT)

    root = ElementTree.fromstring(svg)
    assert root.attrib["width"] == "640"
    assert "Architecture overview  ·  1 app  ·  1 line of code" in texts(svg)
    card = root.findall(f"{SVG}rect")[1]  # [0] is the background
    left = float(card.attrib["x"])
    right = 640 - left - float(card.attrib["width"])
    assert left == pytest.approx(right)


def test_long_names_never_overflow_their_card():
    stack = Stack(
        name="demo",
        apps=[App(name="an-extremely-long-application-folder-name", path="a", kind="api", language="java",
                  technologies=["Spring Boot 3.4"], files=1, lines=1)],
        services=[Service(name="A Very Long Managed Database Service Name", category="database",
                          used_by=["an-extremely-long-application-folder-name"])],
    )

    svg = render_overview(stack, [], LIGHT)

    root = ElementTree.fromstring(svg)
    width = float(root.attrib["width"])
    for element in root.iter(f"{SVG}text"):
        x = float(element.attrib["x"])
        size = float(element.attrib["font-size"])
        weight = int(element.attrib.get("font-weight", 400))
        end = x if element.attrib.get("text-anchor") == "end" else x + text_width(element.text, size, weight)
        assert end <= width, element.text


def test_labels_follow_the_language(shop):
    stack, files = analyse(shop)

    labels = texts(render_overview(stack, files, LIGHT, lang="es"))

    for expected in ["Usuarios", "APLICACIÓN WEB", "Base de datos", "lee y escribe", "inicia sesión",
                     "verifica usuarios", "Generado con repo-xray"]:
        assert expected in labels, expected
    assert any(label.startswith("Visión general de la arquitectura  ·  2 aplicaciones") for label in labels)
