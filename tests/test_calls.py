from pathlib import Path
from textwrap import dedent

from repo_xray.analysis.calls import build_call_graph
from repo_xray.parsers import java, python, typescript


def java_file(path: str, code: str):
    return java.parse(dedent(code).encode(), Path(path))


def short(qualnames):
    return [".".join(q.split(".")[-2:]) for q in qualnames]


def hexagonal_backend():
    return [
        java_file("web/OrderController.java", """
            package shop.web;
            import shop.app.PlaceOrder;
            class OrderController {
                private final PlaceOrder placeOrder;
                Object create() { validate(); return placeOrder.place(OrderMapper.toCommand(null)); }
                private void validate() {}
            }
        """),
        java_file("web/OrderMapper.java", "package shop.web;\nclass OrderMapper { static Object toCommand(Object o) { return o; } }\n"),
        java_file("app/PlaceOrder.java", "package shop.app;\npublic interface PlaceOrder { Object place(Object c); }\n"),
        java_file("app/OrderService.java", """
            package shop.app;
            import shop.app.port.OrderRepository;
            class OrderService implements PlaceOrder {
                private final OrderRepository orders;
                public Object place(Object c) { return orders.save(new Order()); }
            }
        """),
        java_file("app/Order.java", "package shop.app;\nclass Order {}\n"),
        java_file("app/port/OrderRepository.java", "package shop.app.port;\npublic interface OrderRepository { Object save(Object o); }\n"),
        java_file("db/OrderAdapter.java", """
            package shop.db;
            import shop.app.port.OrderRepository;
            class OrderAdapter extends BaseAdapter implements OrderRepository {
                public Object save(Object o) { return jpa.save(o); }
            }
        """),
        java_file("db/BaseAdapter.java", "package shop.db;\nclass BaseAdapter { protected OrderJpa jpa; }\n"),
        java_file("db/OrderJpa.java", "package shop.db;\ninterface OrderJpa { Object save(Object o); }\n"),
    ]


def test_follows_fields_interfaces_and_implementations():
    graph = build_call_graph(hexagonal_backend())

    assert short(graph.calls_from("shop.web.OrderController.create")) == [
        "OrderController.validate", "OrderService.place", "OrderMapper.toCommand",
    ]
    assert short(graph.calls_from("shop.app.OrderService.place")) == ["OrderAdapter.save", "app.Order"]


def test_inherited_fields_and_interfaces_without_implementations():
    graph = build_call_graph(hexagonal_backend())

    assert short(graph.calls_from("shop.db.OrderAdapter.save")) == ["OrderJpa.save"]


def test_typescript_injected_services_and_imported_functions():
    files = [
        typescript.parse(dedent("""
            import { OrdersApi } from '../core/orders-api';
            import { formatTotal as fmt } from '../core/format';
            export class CartPage {
              private readonly api = inject(OrdersApi);
              checkout() { this.api.create(fmt(1)); this.reset(); }
              reset() {}
            }
        """).encode(), Path("src/app/cart/cart-page.ts")),
        typescript.parse(b"export class OrdersApi { create(x: number) { return this.http.post('/api/orders', x); } }\n",
                         Path("src/app/core/orders-api.ts")),
        typescript.parse(b"export function formatTotal(n: number) { return String(n); }\n",
                         Path("src/app/core/format.ts")),
    ]

    graph = build_call_graph(files)

    assert graph.calls_from("src/app/cart/cart-page.CartPage.checkout") == [
        "src/app/core/orders-api.OrdersApi.create",
        "src/app/core/format.formatTotal",
        "src/app/cart/cart-page.CartPage.reset",
    ]


def test_python_methods_and_imported_functions():
    files = [
        python.parse(dedent("""
            from shop.repo import save
            class Service:
                def run(self):
                    self.check()
                    save()
                def check(self):
                    pass
        """), Path("shop/service.py")),
        python.parse("def save():\n    pass\n", Path("shop/repo.py")),
    ]

    graph = build_call_graph(files)

    assert graph.calls_from("shop.service.Service.run") == ["shop.service.Service.check", "shop.repo.save"]


def test_unknown_receivers_stay_unresolved():
    graph = build_call_graph([java_file("A.java", "package p;\nclass A { void f() { list.add(1); helper().go(); } }\n")])

    assert graph.calls_from("p.A.f") == []
