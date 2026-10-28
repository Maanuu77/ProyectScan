from pathlib import Path

from tests.conftest import analyse, write

def detect(root: Path):
    return analyse(root)[0]


def test_apps_with_kind_technologies_and_size(shop):
    stack = detect(shop)

    assert stack.name == shop.name  # no manifest at the root
    api, web = stack.apps
    assert (api.name, api.path, api.kind, api.language) == ("api", "api", "api", "java")
    assert api.technologies == ["Spring Boot 3.4", "Java 21", "JPA"]
    assert (api.files, api.lines) == (1, 3)
    assert (web.name, web.kind, web.language) == ("web", "web", "typescript")
    assert web.technologies == ["Angular 19", "TypeScript 5", "Leaflet"]


def test_services_from_dependencies_imports_compose_and_firebase(shop):
    services = {s.name: s for s in detect(shop).services}

    assert set(services) == {"PostgreSQL", "Redis", "Firebase Auth", "Firebase Storage"}
    postgres = services["PostgreSQL"]
    assert postgres.category == "database"
    assert postgres.used_by == ["api"]
    assert postgres.details == ["PostGIS", "Cloud SQL"]
    assert services["Firebase Auth"].used_by == ["api", "web"]
    assert services["Redis"].used_by == ["api"]  # only in compose: assigned to the API


def test_deployments_and_ci(shop):
    stack = detect(shop)

    api, web = stack.apps
    assert api.deployments == ["Docker", "Cloud Run"]
    assert web.deployments == ["Firebase Hosting"]
    assert stack.ci == ["GitHub Actions"]


def test_single_python_app_at_the_root(tmp_path):
    write(tmp_path, {
        "pyproject.toml": '[project]\nname = "tool"\ndependencies = ["fastapi>=0.110", "sqlalchemy", "psycopg[binary]"]\n',
        "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
    })

    stack = detect(tmp_path)

    (app,) = stack.apps
    assert (app.name, app.path, app.kind, app.language) == ("tool", ".", "api", "python")
    assert app.technologies == ["FastAPI", "Python", "SQLAlchemy"]
    assert [s.name for s in stack.services] == ["PostgreSQL"]


def test_broken_manifests_are_ignored(tmp_path):
    write(tmp_path, {
        "pom.xml": "<project><unclosed>",
        "package.json": "{not json",
        "compose.yaml": "services: [unclosed",
        "src/App.java": "class App {}\n",
    })

    stack = detect(tmp_path)

    assert [a.kind for a in stack.apps] == ["library"]
    assert stack.services == []


def test_project_name_comes_from_a_root_manifest(tmp_path):
    write(tmp_path, {
        "pyproject.toml": '[project]\nname = "repo-xray"\n',
        "main.py": "x = 1\n",
    })

    assert detect(tmp_path).name == "repo-xray"


def test_description_from_readme_then_manifest(tmp_path):
    write(tmp_path, {
        "package.json": '{"name": "shop", "description": "Online shop for second-hand books"}',
        "src/index.ts": "export const x = 1;\n",
    })
    assert detect(tmp_path).description == "Online shop for second-hand books"

    write(tmp_path, {"README.md": "# Shop\n\nBuy and sell second-hand books near you.\n"})
    assert detect(tmp_path).description == "Buy and sell second-hand books near you."


def test_a_root_workspace_manifest_is_not_an_app(tmp_path):
    write(tmp_path, {
        "package.json": '{"name": "shop", "private": true, "workspaces": ["web"]}',
        "web/package.json": '{"dependencies": {"react": "^18.0.0"}}',
        "web/src/App.tsx": "export const App = () => null;\n",
    })

    stack = detect(tmp_path)

    assert stack.name == "shop"
    assert [(a.name, a.kind) for a in stack.apps] == [("web", "web")]
