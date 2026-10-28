import json
import posixpath
import re

from repo_xray.export.markdown import FOLDER, build_documents
from repo_xray.pipeline import analyse
from tests.conftest import JAVA, hexagonal_backend, write


def full_stack(root):
    hexagonal_backend(root)
    write(root, {
        "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0"}}',
        "web/src/app/core/orders-api.ts":
            "export class OrdersApi { create() { return this.http.post(`${this.url}/orders`, {}); } }\n",
        "web/src/app/features/checkout/checkout-page.ts": """\
            import { OrdersApi } from '../../core/orders-api';
            @Component({ selector: 'app-checkout' })
            export class CheckoutPage { private readonly api = inject(OrdersApi); buy() { this.api.create(); } }
        """,
        "web/src/app/features/home/home-page.ts": "@Component({ selector: 'app-home' })\nexport class HomePage {}\n",
    })


def test_bundle_has_index_feature_pages_diagrams_and_json(tmp_path):
    full_stack(tmp_path)

    bundle = build_documents(analyse(tmp_path))

    assert f"{FOLDER}/README.md" in bundle
    assert f"{FOLDER}/features/api-order.md" in bundle
    assert f"{FOLDER}/features/web-checkout.md" in bundle
    for name in ("overview", "features"):
        for theme in ("light", "dark"):
            assert bundle[f"{FOLDER}/images/{name}-{theme}.svg"].startswith("<svg")
    assert any(key.startswith(f"{FOLDER}/images/flow-post-api-orders") for key in bundle)
    data = json.loads(bundle[f"{FOLDER}/analysis.json"])
    assert {f["key"] for f in data["features"]} >= {"api/order", "web/checkout"}


def test_every_link_and_image_points_into_the_bundle(tmp_path):
    full_stack(tmp_path)

    bundle = build_documents(analyse(tmp_path))

    pages = {path: text for path, text in bundle.items() if path.endswith(".md")}
    for path, text in pages.items():
        targets = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r'(?:src|srcset)="([^"]+)"', text)
        for target in targets:
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
            assert resolved in bundle, f"{path} links to missing {target}"


def test_index_summarises_the_project(tmp_path):
    full_stack(tmp_path)

    index = build_documents(analyse(tmp_path))[f"{FOLDER}/README.md"]

    assert index.startswith(f"# {tmp_path.name} architecture")
    assert "an API (`api`) built with Spring Boot" in index
    assert "a web app (`web`) built with Angular 19" in index
    assert '<source media="(prefers-color-scheme: dark)" srcset="images/overview-dark.svg">' in index
    assert "## What happens when…?" in index
    assert "- [Orders](features/api-order.md) — Checkout and order history" in index


def test_feature_page_lists_endpoints_connections_and_files(tmp_path):
    full_stack(tmp_path)

    page = build_documents(analyse(tmp_path))[f"{FOLDER}/features/api-order.md"]

    assert page.startswith("# Orders\n\n> Checkout and order history")
    assert "| `POST` | `/api/orders` |" in page
    assert "- **Called from:** [Checkout](web-checkout.md) (web) · 1 call" in page
    assert "- **Depends on:** [Catalog](api-catalog.md) (api)" in page
    assert f"- `api/{JAVA}/order/domain/Order.java`" in page
