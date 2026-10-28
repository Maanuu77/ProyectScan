from pathlib import Path
from textwrap import dedent

from repo_xray.analysis.stack import detect_stack
from repo_xray.config import Config
from repo_xray.project import analyze_project
from repo_xray.scanner import scan

POM = """\
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.4.1</version>
  </parent>
  <artifactId>shop-api</artifactId>
  <properties><java.version>21</java.version></properties>
  <dependencies>
    <dependency><artifactId>spring-boot-starter-web</artifactId></dependency>
    <dependency><artifactId>spring-boot-starter-data-jpa</artifactId></dependency>
    <dependency><artifactId>postgresql</artifactId></dependency>
    <dependency><artifactId>postgres-socket-factory</artifactId></dependency>
    <dependency><artifactId>firebase-admin</artifactId></dependency>
    <dependency><artifactId>testcontainers-postgresql</artifactId><scope>test</scope></dependency>
  </dependencies>
</project>
"""

PACKAGE_JSON = """\
{
  "name": "shop-web",
  "dependencies": {"@angular/core": "^19.2.0", "@angular/fire": "^19.0.0", "leaflet": "^1.9.4"},
  "devDependencies": {"typescript": "~5.6.0", "jasmine-core": "^5.0.0"}
}
"""


def write(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(content), encoding="utf-8")


def detect(root: Path):
    scan_result = scan(root, Config())
    return detect_stack(scan_result, analyze_project(scan_result))


def make_shop(root: Path) -> None:
    write(root, {
        "api/pom.xml": POM,
        "api/Dockerfile": "FROM eclipse-temurin:21\n",
        "api/src/main/java/shop/Auth.java": "package shop;\nimport com.google.firebase.auth.FirebaseAuth;\nclass Auth {}\n",
        "api/src/main/resources/application.yml": "spring:\n  datasource:\n    url: jdbc:postgresql://db/shop\n",
        "web/package.json": PACKAGE_JSON,
        "web/src/app/auth.ts": "import { Auth } from '@angular/fire/auth';\nexport class AuthService {}\n",
        "web/e2e/package.json": '{"devDependencies": {"@playwright/test": "^1.0.0"}}',
        "compose.yaml": "services:\n  db:\n    image: postgis/postgis:17-3.5\n  cache:\n    image: redis:7\n",
        "firebase.json": '{"hosting": {"public": "web/dist/browser"}, "storage": {"rules": "x"}}',
        "deploy/service.yaml": "apiVersion: serving.knative.dev/v1\nkind: Service\n",
        ".github/workflows/ci.yml": "name: CI\n",
    })


def test_apps_with_kind_technologies_and_size(tmp_path):
    make_shop(tmp_path)

    stack = detect(tmp_path)

    assert stack.name == tmp_path.name
    api, web = stack.apps
    assert (api.name, api.path, api.kind, api.language) == ("api", "api", "api", "java")
    assert api.technologies == ["Spring Boot 3.4", "Java 21", "JPA"]
    assert (api.files, api.lines) == (1, 3)
    assert (web.name, web.kind, web.language) == ("web", "web", "typescript")
    assert web.technologies == ["Angular 19", "TypeScript 5", "Leaflet"]


def test_services_from_dependencies_imports_compose_and_firebase(tmp_path):
    make_shop(tmp_path)

    services = {s.name: s for s in detect(tmp_path).services}

    assert set(services) == {"PostgreSQL", "Redis", "Firebase Auth", "Firebase Storage"}
    postgres = services["PostgreSQL"]
    assert postgres.category == "database"
    assert postgres.used_by == ["api"]
    assert postgres.details == ["PostGIS", "Cloud SQL"]
    assert services["Firebase Auth"].used_by == ["api", "web"]
    assert services["Redis"].used_by == ["api"]  # only in compose: assigned to the API


def test_deployments_and_ci(tmp_path):
    make_shop(tmp_path)

    stack = detect(tmp_path)

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
    assert (app.name, app.path, app.kind, app.language) == (tmp_path.name, ".", "api", "python")
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
