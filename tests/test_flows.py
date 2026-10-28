from repo_xray.analysis.calls import build_call_graph
from repo_xray.analysis.features import detect_features
from repo_xray.analysis.flows import build_flows, pick_flows
from repo_xray.analysis.linking import link_http_calls
from tests.conftest import JAVA, analyse, write


def flows_of(root):
    stack, files = analyse(root)
    graph, links = build_call_graph(files), link_http_calls(files)
    return build_flows(stack, files, graph, links, detect_features(stack, files, graph, links))


def shop_with_database(root):
    write(root, {
        "api/pom.xml": "<project><dependencies>"
                       "<dependency><artifactId>spring-boot-starter-web</artifactId></dependency>"
                       "<dependency><artifactId>postgresql</artifactId></dependency>"
                       "</dependencies></project>",
        f"api/{JAVA}/order/infrastructure/web/OrderController.java": """\
            package shop.order.infrastructure.web;
            import shop.order.application.PlaceOrder;
            @RestController
            class OrderController {
                private final PlaceOrder placeOrder;
                private final OrderWebMapper mapper;
                @PostMapping("/api/orders")
                @Operation(summary = "Place an order")
                Object create() { return mapper.toResponse(placeOrder.place()); }
                @GetMapping("/api/orders/{id}")
                Object one() { return null; }
            }
        """,
        f"api/{JAVA}/order/infrastructure/web/OrderWebMapper.java":
            "package shop.order.infrastructure.web;\nclass OrderWebMapper { Object toResponse(Object o) { return o; } }\n",
        f"api/{JAVA}/order/application/PlaceOrder.java":
            "package shop.order.application;\npublic interface PlaceOrder { Object place(); }\n",
        f"api/{JAVA}/order/application/OrderRepository.java":
            "package shop.order.application;\npublic interface OrderRepository { Object save(); }\n",
        f"api/{JAVA}/order/application/OrderService.java": """\
            package shop.order.application;
            class OrderService implements PlaceOrder {
                private final OrderRepository orders;
                public Object place() { check(); return orders.save(); }
                private void check() {}
            }
        """,
        f"api/{JAVA}/order/domain/Order.java": "package shop.order.domain;\nrecord Order(String id) {}\n",
        f"api/{JAVA}/order/infrastructure/persistence/OrderAdapter.java": """\
            package shop.order.infrastructure.persistence;
            import shop.order.application.OrderRepository;
            class OrderAdapter implements OrderRepository {
                public Object save() { return helper(); }
                private Object helper() { return null; }
            }
        """,
        f"api/{JAVA}/catalog/infrastructure/web/ProductController.java": """\
            package shop.catalog.infrastructure.web;
            @RestController
            class ProductController { @GetMapping("/api/products") Object all() { return null; } }
        """,
        f"api/{JAVA}/catalog/domain/Product.java": "package shop.catalog.domain;\nrecord Product(String id) {}\n",
        "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0"}}',
        "web/src/app/core/orders-api.ts":
            "export class OrdersApi { create() { return this.http.post(`${this.url}/orders`, {}); } }\n",
        "web/src/app/features/checkout/checkout-page.ts": """\
            import { OrdersApi } from '../../core/orders-api';
            @Component({ selector: 'app-checkout' })
            export class CheckoutPage {
              private readonly api = inject(OrdersApi);
              buy() { this.submit(); }
              private submit() { this.api.create(); }
            }
        """,
        "web/src/app/features/catalog/catalog-page.ts":
            "@Component({ selector: 'app-catalog' })\nexport class CatalogPage {}\n",
    })


def test_flow_from_screen_to_database(tmp_path):
    shop_with_database(tmp_path)

    flows = {f.route: f for f in flows_of(tmp_path)}

    flow = flows["/api/orders"]
    assert (flow.title, flow.method, flow.feature) == ("Place an order", "POST", "api/order")
    assert [(s.app, s.layer, s.name) for s in flow.steps] == [
        ("web", "entry", "CheckoutPage.buy"),  # the method the user triggers, not its helper
        ("web", "data", "OrdersApi.create"),
        ("api", "entry", "OrderController.create"),
        ("api", "application", "OrderService.place"),
        ("api", "data", "OrderAdapter.save"),
        ("PostgreSQL", "service", "PostgreSQL"),
    ]
    assert flow.http_index == 2


def test_flows_without_a_frontend_start_at_the_endpoint(tmp_path):
    shop_with_database(tmp_path)

    flow = {f.route: f for f in flows_of(tmp_path)}["/api/orders/{id}"]

    assert flow.title == "GET /api/orders/{id}"
    assert flow.http_index is None
    assert [s.name for s in flow.steps] == ["OrderController.one"]


def test_pick_prefers_complete_writes_and_one_flow_per_feature(tmp_path):
    shop_with_database(tmp_path)

    picked = pick_flows(flows_of(tmp_path), limit=3)

    assert [f.route for f in picked] == ["/api/orders", "/api/products"]
