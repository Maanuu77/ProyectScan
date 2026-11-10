"""HTTP endpoints of Python and NestJS backends, and the flows that start at them."""

from pathlib import Path
from textwrap import dedent

from repo_xray.parsers import python, typescript
from repo_xray.pipeline import analyse
from tests.conftest import write


def endpoints(source: str, parser=python, name: str = "app/api.py") -> list[tuple[str, str, str, str | None]]:
    info = parser.parse(dedent(source).encode("utf-8"), Path(name))
    return [(e.method, e.path, e.handler.rpartition(".")[2], e.summary) for e in info.endpoints]


def test_fastapi_routes_with_router_prefix_and_summaries():
    found = endpoints('''
        from fastapi import APIRouter, FastAPI

        app = FastAPI()
        router = APIRouter(prefix="/orders", tags=["orders"])

        @app.get("/health")
        def health():
            return "ok"

        @router.get("", summary="List the orders")
        async def list_orders(): ...

        @router.post("/")
        def create_order():
            """Place an order.

            More about it."""

        @router.get("/{order_id:int}/lines/{line_id}")
        def one_line(order_id: int, line_id: int): ...

        @app.api_route("/search", methods=["GET", "POST"])
        def search(): ...
    ''')

    assert found == [
        ("GET", "/health", "health", None),
        ("GET", "/orders", "list_orders", "List the orders"),
        ("POST", "/orders", "create_order", "Place an order"),
        ("GET", "/orders/{order_id}/lines/{line_id}", "one_line", None),
        ("GET", "/search", "search", None),
        ("POST", "/search", "search", None),
    ]


def test_flask_routes_with_blueprint_prefix_methods_and_converters():
    found = endpoints('''
        from flask import Blueprint, Flask

        app = Flask(__name__)
        bp = Blueprint("items", __name__, url_prefix="/api/items")

        @app.route("/")
        def home(): ...

        @bp.route("/<int:item_id>", methods=["GET", "DELETE"])
        def item(item_id): ...

        @bp.post("/<name>/tags")
        def tag(name): ...
    ''')

    assert found == [
        ("GET", "/", "home", None),
        ("GET", "/api/items/{item_id}", "item", None),
        ("DELETE", "/api/items/{item_id}", "item", None),
        ("POST", "/api/items/{name}/tags", "tag", None),
    ]


def test_decorators_that_are_not_routes_are_left_alone():
    found = endpoints('''
        @cache.get("orders")
        def cached(): ...

        @app.get(ROUTE)
        def computed(): ...

        @retry.route
        def plain(): ...

        @functools.lru_cache(maxsize=10)
        def memo(): ...

        @app.websocket("/ws")
        def socket(): ...
    ''')

    assert found == []  # no slash, a computed path, no call, another decorator, not HTTP


def test_nestjs_controllers():
    found = endpoints('''
        @Controller('orders')
        export class OrdersController {
          constructor(private readonly orders: OrdersService) {}

          @Get()
          findAll() { return this.orders.findAll(); }

          /** Read one order. */
          @Get(':id/lines/:lineId')
          findLine() {}

          @ApiOperation({ summary: 'Place an order' })
          @Post()
          create() {}

          @All('ping')
          ping() {}

          helper() {}
        }

        @Controller({ path: 'admin', version: '1' })
        export class AdminController {
          @Delete(':id')
          remove() {}
        }

        export class NotAController {
          @Get('x')
          nothing() {}
        }
    ''', typescript, "src/orders/orders.controller.ts")

    assert found == [
        ("GET", "/orders", "findAll", None),
        ("GET", "/orders/{id}/lines/{lineId}", "findLine", "Read one order."),
        ("POST", "/orders", "create", "Place an order"),
        ("ANY", "/orders/ping", "ping", None),
        ("DELETE", "/admin/{id}", "remove", None),
    ]


def test_a_fastapi_project_gets_flows_from_the_screen_to_the_handler_and_beyond(tmp_path):
    write(tmp_path, {
        "api/pyproject.toml": '[project]\nname = "api"\ndependencies = ["fastapi", "psycopg"]\n',
        "api/app/routers/orders.py": '''\
            from fastapi import APIRouter
            from app.services import orders as order_service

            router = APIRouter(prefix="/orders")

            @router.post("", summary="Place an order")
            def create_order():
                return order_service.place()
        ''',
        "api/app/services/orders.py": '''\
            from app.repositories.orders import save

            def place():
                return save()
        ''',
        "api/app/repositories/orders.py": "import psycopg\n\ndef save():\n    return 1\n",
        "web/package.json": '{"dependencies": {"react": "^19.0.0"}}',
        "web/src/api/orders.ts": "export const placeOrder = () => fetch(`${BASE}/orders`, { method: 'POST' });\n",
        "web/src/pages/Checkout.tsx": "import { placeOrder } from '../api/orders';\n"
                                      "export function Checkout() { return placeOrder(); }\n",
    })

    analysis = analyse(tmp_path)

    flow = next(f for f in analysis.flows if f.route == "/orders")
    assert (flow.method, flow.title) == ("POST", "Place an order")
    assert [step.name for step in flow.steps] == ["Checkout", "placeOrder", "create_order", "place", "save", "PostgreSQL"]
    assert flow.http_index == 2
    assert "no-flows" not in [d.code for d in analysis.diagnostics]
    assert len(analysis.links) == 1


def test_a_nestjs_project_gets_flows_through_injected_services(tmp_path):
    write(tmp_path, {
        "package.json": '{"name": "shop-api", "dependencies": {"@nestjs/core": "^11.0.0"}}',
        "src/orders/orders.controller.ts": '''\
            import { OrdersService } from './orders.service';
            @Controller('orders')
            export class OrdersController {
              constructor(private readonly orders: OrdersService) {}
              @Post()
              create() { return this.orders.place(); }
            }
        ''',
        "src/orders/orders.service.ts": '''\
            import { OrdersRepository } from './orders.repository';
            @Injectable()
            export class OrdersService {
              constructor(private readonly repository: OrdersRepository) {}
              place() { return this.repository.save(); }
            }
        ''',
        "src/orders/orders.repository.ts": "export class OrdersRepository { save() { return 1; } }\n",
    })

    analysis = analyse(tmp_path)

    flow = next(f for f in analysis.flows if f.route == "/orders")
    assert [step.name for step in flow.steps] == ["OrdersController.create", "OrdersService.place", "OrdersRepository.save"]
    assert analysis.stack.apps[0].kind == "api"
