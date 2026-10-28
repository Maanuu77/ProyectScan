"""Shared sample projects for the analysis and rendering tests."""

from pathlib import Path
from textwrap import dedent

import pytest

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


def analyse(root: Path):
    scan_result = scan(root, Config())
    files = analyze_project(scan_result)
    return detect_stack(scan_result, files), files


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


@pytest.fixture
def shop(tmp_path: Path) -> Path:
    """A full-stack project: Spring API, Angular web app, Postgres, Redis and Firebase."""
    make_shop(tmp_path)
    return tmp_path
