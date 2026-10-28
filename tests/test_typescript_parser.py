from pathlib import Path
from textwrap import dedent

from repo_xray.parsers.typescript import parse


def parse_ts(code: str, path: str = "src/app/orders/orders-api.ts"):
    return parse(dedent(code).encode(), Path(path))


def by_name(info):
    return {s.name: s for s in info.symbols}


def test_file_metadata():
    info = parse_ts("export const x = 1;\n")

    assert info.language == "typescript"
    assert info.name == "src/app/orders/orders-api"
    assert info.package == "src/app/orders"
    assert parse_ts("x;", "web/main.js").language == "javascript"


def test_imports_resolve_relative_paths():
    info = parse_ts("""
        import { HttpClient } from '@angular/common/http';
        import { Order as O, Page } from '../core/models';
        import api, * as all from './api';
        import './styles.css';
    """)

    assert [(i.module, i.name, i.alias) for i in info.imports] == [
        ("@angular/common/http", "HttpClient", None),
        ("src/app/core/models", "Order", "O"),
        ("src/app/core/models", "Page", None),
        ("src/app/orders/api", "default", "api"),
        ("src/app/orders/api", "*", "all"),
        ("src/app/orders/styles.css", None, None),
    ]


def test_angular_service_with_decorators_fields_and_jsdoc():
    info = parse_ts("""
        /** Talks to the orders endpoints. */
        @Injectable({ providedIn: 'root' })
        export class OrdersApi extends BaseApi implements OnInit {
          private readonly http = inject(HttpClient);
          items: Order[] = [];
          total: Signal<number>;

          constructor(private readonly auth: AuthService, plain: string) {
            super();
          }

          async load(): Promise<void> {}
        }
    """)

    api = by_name(info)["OrdersApi"]
    assert api.kind == "class"
    assert api.docstring == "Talks to the orders endpoints."
    assert api.decorators == ["Injectable({ providedIn: 'root' })"]
    assert api.bases == ["BaseApi", "OnInit"]
    assert api.fields == {"http": "HttpClient", "total": "Signal", "auth": "AuthService"}
    assert by_name(info)["load"].is_async
    assert by_name(info)["load"].qualname == "src/app/orders/orders-api.OrdersApi.load"


def test_react_components_hooks_and_plain_functions():
    info = parse_ts("""
        /** Shows one order. */
        export const OrderCard = ({ order }: Props) => <div>{order.id}</div>;
        export function useOrders() { return useState([]); }
        const handler = async function () {};
        const notAFunction = 3;
    """, "src/components/OrderCard.tsx")

    symbols = by_name(info)
    assert set(symbols) == {"OrderCard", "useOrders", "handler"}
    assert symbols["OrderCard"].docstring == "Shows one order."
    assert symbols["handler"].is_async


def test_interfaces_enums_and_class_members():
    info = parse_ts("""
        export interface Order extends Base { id: string }
        enum Status { New, Paid }
        class View {
          @Input() order!: Order;
          @HostListener('click')
          onClick() {}
          refresh = () => this.load();
        }
    """)

    symbols = by_name(info)
    assert symbols["Order"].kind == "interface"
    assert symbols["Order"].bases == ["Base"]
    assert symbols["Status"].kind == "enum"
    assert symbols["onClick"].decorators == ["HostListener('click')"]
    assert symbols["refresh"].kind == "method"
    assert symbols["View"].fields == {"order": "Order"}


def test_calls_record_dotted_callees_and_constructors():
    info = parse_ts("""
        class Page {
          save() {
            this.api.create(this.form.value).subscribe(() => this.router.navigate(['/']));
            new Toast('saved');
            getStore().dispatch();
          }
        }
    """)

    assert [c.callee for c in info.calls] == [
        "this.api.create",
        "this.router.navigate",
        "new Toast",
        "getStore",
    ]
    assert {c.caller for c in info.calls} == {"src/app/orders/orders-api.Page.save"}


def test_http_calls_from_angular_fetch_and_axios():
    info = parse_ts("""
        class OrdersApi {
          one(id: string) { return this.http.get<Order>(`${this.url}/orders/${id}`); }
          create(o: Order) { return this.httpClient.post(API + '/orders', o); }
          remove(id: string) { return fetch('/api/orders/' + id, { method: 'DELETE' }); }
          list() { return fetch(`/api/orders`); }
          search(q: string) { return axios.get(url); }
          notHttp() { return this.cache.get('orders'); }
        }
    """)

    assert [(h.method, h.url, h.caller.rpartition(".")[2]) for h in info.http_calls] == [
        ("GET", "{this.url}/orders/{id}", "one"),
        ("POST", "{API}/orders", "create"),
        ("DELETE", "/api/orders/{id}", "remove"),
        ("GET", "/api/orders", "list"),
        ("GET", "{url}", "search"),
    ]
