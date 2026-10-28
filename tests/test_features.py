from repo_xray.analysis.calls import build_call_graph
from repo_xray.analysis.features import detect_features
from repo_xray.analysis.linking import link_http_calls
from tests.conftest import analyse, write

JAVA = "src/main/java/shop"


def features_of(root):
    stack, files = analyse(root)
    return detect_features(stack, files, build_call_graph(files), link_http_calls(files))


def by_key(feature_map):
    return {f.key: f for f in feature_map.features}


def hexagonal_backend(root):
    write(root, {
        "api/pom.xml": "<project><dependencies><dependency><artifactId>spring-boot-starter-web</artifactId>"
                       "</dependency></dependencies></project>",
        f"api/{JAVA}/order/infrastructure/web/OrderController.java": """\
            package shop.order.infrastructure.web;
            import shop.order.application.PlaceOrder;
            @RestController
            @Tag(name = "Orders", description = "Checkout and order history")
            class OrderController {
                private final PlaceOrder placeOrder;
                @PostMapping("/api/orders") Object create() { return placeOrder.place(); }
            }
        """,
        f"api/{JAVA}/order/application/PlaceOrder.java": "package shop.order.application;\npublic interface PlaceOrder { Object place(); }\n",
        f"api/{JAVA}/order/application/OrderService.java": """\
            package shop.order.application;
            import shop.catalog.application.FindProduct;
            class OrderService implements PlaceOrder {
                private final FindProduct products;
                public Object place() { return products.find(); }
            }
        """,
        f"api/{JAVA}/order/domain/Order.java": "package shop.order.domain;\nrecord Order(String id) {}\n",
        f"api/{JAVA}/catalog/infrastructure/web/ProductController.java": """\
            package shop.catalog.infrastructure.web;
            /** Browse the product catalogue. */
            @RestController
            class ProductController { @GetMapping("/api/products") Object all() { return null; } }
        """,
        f"api/{JAVA}/catalog/application/FindProduct.java": "package shop.catalog.application;\npublic interface FindProduct { Object find(); }\n",
        f"api/{JAVA}/catalog/domain/Product.java": "package shop.catalog.domain;\nrecord Product(String id) {}\n",
        f"api/{JAVA}/shared/infrastructure/SecurityConfig.java": "package shop.shared.infrastructure;\nclass SecurityConfig {}\n",
    })


def test_vertical_slices_become_features(tmp_path):
    hexagonal_backend(tmp_path)

    feature_map = features_of(tmp_path)

    features = by_key(feature_map)
    assert set(features) == {"api/order", "api/catalog"}
    order = features["api/order"]
    assert order.name == "Orders"  # from the OpenAPI tag
    assert order.description == "Checkout and order history"
    assert order.path == f"api/{JAVA}/order"
    assert order.layers == {"entry": 1, "application": 2, "domain": 1}
    assert [e.path for e in order.endpoints] == ["/api/orders"]
    assert features["api/catalog"].name == "Catalog"
    assert features["api/catalog"].description == "Browse the product catalogue"
    assert [(s.app, s.name, s.files) for s in feature_map.shared] == [("api", "shared", 1)]


def test_same_app_dependencies_follow_the_call_graph(tmp_path):
    hexagonal_backend(tmp_path)

    features = by_key(features_of(tmp_path))

    assert features["api/order"].depends_on == {"api/catalog": 1}
    assert features["api/catalog"].depends_on == {}


def test_frontend_features_link_to_backend_features_through_api_clients(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, {
        "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0", "@angular/fire": "^19.0.0"}}',
        "web/src/app/core/orders-api.ts": """\
            export class OrdersApi {
              create() { return this.http.post(`${this.url}/orders`, {}); }
              products() { return this.http.get(`${this.url}/products`); }
            }
        """,
        "web/src/app/core/auth.service.ts": "import { Auth } from '@angular/fire/auth';\nexport class AuthService { login() {} }\n",
        "web/src/app/features/checkout/checkout-page.ts": """\
            import { OrdersApi } from '../../core/orders-api';
            @Component({ selector: 'app-checkout' })
            export class CheckoutPage {
              private readonly api = inject(OrdersApi);
              buy() { this.api.products(); this.api.create(); }
            }
        """,
        "web/src/app/features/login/login-page.ts": """\
            import { AuthService } from '../../core/auth.service';
            @Component({ selector: 'app-login' })
            export class LoginPage { constructor(private auth: AuthService) {} go() { this.auth.login(); } }
        """,
    })

    feature_map = features_of(tmp_path)

    features = by_key(feature_map)
    assert features["web/checkout"].calls == {"api/catalog": 1, "api/order": 1}
    assert features["web/login"].calls == {}
    assert features["web/login"].services == ["Firebase Auth"]
    assert [s.name for s in feature_map.shared if s.app == "web"] == ["core"]


def test_layer_first_projects_group_files_by_name(tmp_path):
    write(tmp_path, {
        "pyproject.toml": '[project]\nname = "shop"\ndependencies = ["flask"]\n',
        "shop/routes/cart_routes.py": "def cart():\n    pass\n",
        "shop/services/cart_service.py": "def add():\n    pass\n",
        "shop/repositories/cart_repository.py": "def save():\n    pass\n",
        "shop/routes/invoice_routes.py": "def invoices():\n    pass\n",
        "shop/services/invoice_service.py": "def total():\n    pass\n",
        "shop/utils/dates.py": "def today():\n    pass\n",
    })

    feature_map = features_of(tmp_path)

    features = by_key(feature_map)
    assert set(features) == {"shop/cart", "shop/invoice"}
    assert features["shop/cart"].layers == {"entry": 1, "application": 1, "data": 1}
    assert features["shop/invoice"].name == "Invoice"
    assert [s.name for s in feature_map.shared] == ["utils"]


def test_small_projects_are_a_single_feature(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "tool"\n', "tool.py": "def main():\n    pass\n"})

    (feature,) = features_of(tmp_path).features

    assert (feature.key, feature.name, len(feature.files)) == ("tool/tool", "Tool", 1)
