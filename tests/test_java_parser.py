from pathlib import Path
from textwrap import dedent

from repo_xray.parsers.java import parse


def parse_java(code: str, path: str = "src/main/java/com/shop/web/OrderController.java"):
    return parse(dedent(code).encode(), Path(path))


def by_qualname(info):
    return {s.qualname: s for s in info.symbols}


def test_file_metadata():
    info = parse_java("""
        package com.shop.web;

        class OrderController {}
    """)

    assert info.language == "java"
    assert info.package == "com.shop.web"
    assert info.name == "com.shop.web.OrderController"
    assert info.error is None


def test_types_with_bases_annotations_fields_and_javadoc():
    info = parse_java("""
        package com.shop.app;

        /**
         * Places orders.
         * @author someone
         */
        @Service
        @Transactional(readOnly = true)
        public class OrderService extends BaseService<Order> implements PlaceOrder, CancelOrder {
            private final OrderRepository orders;
            private final List<Item> items, extras;

            interface Listener {}
            enum Status { NEW, PAID }
        }

        record OrderView(UUID id, Money total) {}
    """, "OrderService.java")

    symbols = by_qualname(info)
    service = symbols["com.shop.app.OrderService"]
    assert service.kind == "class"
    assert service.docstring == "Places orders."
    assert service.decorators == ["Service", "Transactional(readOnly = true)"]
    assert service.bases == ["BaseService", "PlaceOrder", "CancelOrder"]
    assert service.fields == {"orders": "OrderRepository", "items": "List", "extras": "List"}

    assert symbols["com.shop.app.OrderService.Listener"].kind == "interface"
    assert symbols["com.shop.app.OrderService.Status"].kind == "enum"
    view = symbols["com.shop.app.OrderView"]
    assert view.kind == "record"
    assert view.fields == {"id": "UUID", "total": "Money"}


def test_methods_and_constructors():
    info = parse_java("""
        package p;
        class Repo {
            Repo(DataSource ds) {}

            /** Finds one. */
            @Override
            public Optional<Order> find(UUID id) { return Optional.empty(); }
        }
    """, "Repo.java")

    symbols = by_qualname(info)
    assert symbols["p.Repo.Repo"].kind == "method"
    find = symbols["p.Repo.find"]
    assert find.parent == "p.Repo"
    assert find.docstring == "Finds one."
    assert find.decorators == ["Override"]
    assert (find.lineno, find.end_lineno) == (7, 8)  # starts at its annotation


def test_imports():
    info = parse_java("""
        package p;
        import com.shop.domain.Order;
        import static java.util.Objects.requireNonNull;
        import java.util.*;
        class A {}
    """, "A.java")

    assert [(i.module, i.name) for i in info.imports] == [
        ("com.shop.domain", "Order"),
        ("java.util.Objects", "requireNonNull"),
        ("java.util", "*"),
    ]


def test_calls_keep_simple_receivers_and_skip_chains():
    info = parse_java("""
        package p;
        class Service {
            void run() {
                orders.save(mapper.toEntity(request));
                this.events.publish(new OrderPlaced(id));
                validate();
                list.stream().map(mapper::toView);
            }
        }
    """, "Service.java")

    assert [(c.caller, c.callee) for c in info.calls] == [
        ("p.Service.run", "orders.save"),
        ("p.Service.run", "mapper.toEntity"),
        ("p.Service.run", "this.events.publish"),
        ("p.Service.run", "new OrderPlaced"),
        ("p.Service.run", "validate"),
        ("p.Service.run", "list.stream"),
        ("p.Service.run", "mapper.toView"),
    ]


def test_spring_endpoints_with_class_prefix():
    info = parse_java("""
        package p;
        @RestController
        @RequestMapping("/api/orders")
        class OrderController {
            @GetMapping
            List<Order> all() { return null; }

            /** Creates an order. */
            @PostMapping({"", "/new"})
            Order create() { return null; }

            @GetMapping(path = "/{id}")
            @Operation(summary = "One order")
            Order one(@PathVariable UUID id) { return null; }

            @RequestMapping(value = "/{id}", method = RequestMethod.DELETE)
            void delete(UUID id) {}
        }
    """, "OrderController.java")

    assert [(e.method, e.path, e.handler, e.summary) for e in info.endpoints] == [
        ("GET", "/api/orders", "p.OrderController.all", None),
        ("POST", "/api/orders", "p.OrderController.create", "Creates an order."),
        ("POST", "/api/orders/new", "p.OrderController.create", "Creates an order."),
        ("GET", "/api/orders/{id}", "p.OrderController.one", "One order"),
        ("DELETE", "/api/orders/{id}", "p.OrderController.delete", None),
    ]


def test_broken_source_is_parsed_as_far_as_possible():
    info = parse_java("""
        package p;
        class Ok { void fine() {} }
        class Broken { void oops( }
    """, "Ok.java")

    assert "p.Ok.fine" in by_qualname(info)
