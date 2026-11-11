from repo_xray.app import navigation as nav
from repo_xray.app.navigation import DIAGRAM, ENTRY, GROUP, NOTE, PAGE, SECTION, Target
from repo_xray.export.markdown import FOLDER, build_documents, diagram_path, feature_page
from repo_xray.pipeline import analyse
from repo_xray.render import ids
from tests.conftest import hexagonal_backend, write

WEB = {
    "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0"}}',
    "web/src/app/features/checkout/checkout.page.ts": """\
        import { OrdersApi } from '../../core/orders.api';
        @Component({})
        export class CheckoutPage {
          private api = inject(OrdersApi);
          buy() { this.api.create(); }
        }
    """,
    "web/src/app/features/catalog/catalog.page.ts": "@Component({})\nexport class CatalogPage {}\n",
    "web/src/app/core/orders.api.ts": """\
        export class OrdersApi {
          constructor(private http: HttpClient) {}
          create() { return this.http.post('/api/orders', {}); }
        }
    """,
}


def full_stack(tmp_path):
    hexagonal_backend(tmp_path)
    write(tmp_path, WEB)
    return analyse(tmp_path)


def rows(navigation) -> list[tuple[str, str]]:
    return [(item.kind, item.title) for item in navigation.items]


def test_documents_are_grouped_by_level_frontends_first(tmp_path):
    navigation = nav.build(full_stack(tmp_path))

    assert rows(navigation) == [
        (SECTION, "Overview"), (ENTRY, "Architecture"), (ENTRY, "Summary"), (ENTRY, "Analysis report"),
        (SECTION, "Features"), (ENTRY, "Feature map"),
        (GROUP, "web"), (ENTRY, "Catalog"), (ENTRY, "Checkout"),
        (GROUP, "api"), (ENTRY, "Catalog"), (ENTRY, "Orders"),
        (SECTION, "Flows"), (GROUP, "Key flows"), (ENTRY, "POST /api/orders"), (ENTRY, "GET /api/products"),
    ]


def test_every_entry_leads_to_a_document_of_the_bundle(tmp_path):
    analysis = full_stack(tmp_path)
    bundle = build_documents(analysis)

    for item in nav.build(analysis).entries():
        target = item.target
        if target.kind == DIAGRAM:
            assert diagram_path(target.name, "light") in bundle and diagram_path(target.name, "dark") in bundle
        elif target.kind == PAGE:
            assert target.name in bundle
        else:
            assert target == nav.REPORT_PAGE


def test_sections_count_what_they_hold_and_flows_show_their_method(tmp_path):
    navigation = nav.build(full_stack(tmp_path))

    sections = {item.title: item.badge for item in navigation.items if item.kind == SECTION}
    assert sections == {"Overview": "", "Features": "4", "Flows": "2"}
    flow = next(item for item in navigation.entries() if item.title == "POST /api/orders")
    assert (flow.badge, flow.badge_tone, flow.icon) == ("POST", "method", "flow")
    assert flow.target == Target(DIAGRAM, "flow-post-api-orders")


def test_flows_beyond_the_key_ones_are_listed_under_their_feature_once(tmp_path):
    hexagonal_backend(tmp_path)
    controller = tmp_path / "api/src/main/java/shop/order/infrastructure/web/OrderController.java"
    controller.write_text(controller.read_text(encoding="utf-8").replace(
        '@PostMapping("/api/orders") Object create() { return placeOrder.place(); }',
        '@PostMapping("/api/orders") Object create() { return placeOrder.place(); }\n'
        '    @GetMapping("/api/orders") Object list() { return null; }\n'
        '    @DeleteMapping("/api/orders/{id}") Object remove() { return null; }'), encoding="utf-8")

    navigation = nav.build(analyse(tmp_path))

    flows = rows(navigation)[rows(navigation).index((SECTION, "Flows")) + 1:]
    assert flows[0] == (GROUP, "Key flows")
    assert (GROUP, "Orders") in flows  # the flows of Orders that are not key flows
    titles = [title for kind, title in flows if kind == ENTRY]
    assert len(titles) == len(set(titles)) == 4  # no flow is listed twice


def test_an_app_without_endpoints_explains_the_empty_level(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "tool"\n', "tool.py": "x = 1\n"})

    navigation = nav.build(analyse(tmp_path))

    note = next(item for item in navigation.items if item.kind == NOTE)
    assert note.title == "No flows found" and "endpoints" in note.hint
    assert navigation.home(nav.FLOWS) is None
    assert navigation.home(nav.FEATURES) == nav.FEATURES_DIAGRAM


def test_the_report_shows_how_many_warnings_there_are(tmp_path):
    hexagonal_backend(tmp_path)
    clean = nav.build(analyse(tmp_path)).find(nav.REPORT_PAGE)
    write(tmp_path, {"api/tools/bad.py": "def broken(:\n"})
    broken = nav.build(analyse(tmp_path)).find(nav.REPORT_PAGE)

    assert clean.badge_tone == "" and clean.badge.isdigit()  # notes only: a plain count
    assert (broken.badge, broken.badge_tone) == ("1", "warning")


def test_filter_keeps_the_headings_of_what_matches(tmp_path):
    navigation = nav.build(full_stack(tmp_path))

    assert rows(navigation.filtered("checkout")) == [  # by name, and by description ("Checkout and order history")
        (SECTION, "Features"), (GROUP, "web"), (ENTRY, "Checkout"), (GROUP, "api"), (ENTRY, "Orders")]
    assert rows(navigation.filtered("POST orders")) == [(SECTION, "Flows"), (GROUP, "Key flows"),
                                                         (ENTRY, "POST /api/orders")]  # the route is searched too
    assert [title for kind, title in rows(navigation.filtered("api catalog")) if kind == ENTRY] == ["Catalog"]
    assert navigation.filtered("nothing like this").items == []
    assert navigation.filtered("   ") is navigation


def test_levels_have_a_home_and_entries_have_neighbours(tmp_path):
    navigation = nav.build(full_stack(tmp_path))

    assert navigation.home(nav.OVERVIEW) == nav.OVERVIEW_DIAGRAM
    assert navigation.home(nav.FEATURES) == nav.FEATURES_DIAGRAM
    assert navigation.home(nav.FLOWS) == Target(DIAGRAM, "flow-post-api-orders")
    assert navigation.neighbour(nav.OVERVIEW_DIAGRAM, 1) == nav.SUMMARY_PAGE
    assert navigation.neighbour(nav.OVERVIEW_DIAGRAM, -1) is None  # no wrapping around
    assert navigation.neighbour(Target(PAGE, "missing.md"), 1) is None


def test_a_click_on_a_card_leads_to_what_it_stands_for(tmp_path):
    analysis = full_stack(tmp_path)

    assert nav.target_of_element(analysis, ids.feature_id("api/order")) == Target(PAGE, feature_page("api/order"))
    assert nav.target_of_element(analysis, ids.step_id(3, "api/order")) == Target(PAGE, feature_page("api/order"))
    assert nav.target_of_element(analysis, ids.app_id("web")) == nav.FEATURES_DIAGRAM
    assert nav.target_of_element(analysis, ids.service_id("PostgreSQL")) == nav.REPORT_PAGE
    assert nav.target_of_element(analysis, ids.step_id(2, None)) is None
    assert nav.target_of_element(analysis, ids.feature_id("api/unknown")) is None
    assert nav.target_of_element(analysis, "anything") is None
    assert nav.SUMMARY_PAGE == Target(PAGE, f"{FOLDER}/README.md")
