import pytest

from repo_xray.analysis.features import Feature, FeatureMap
from repo_xray.analysis.stack import Stack
from repo_xray.analysis.texts import clean_title, describe_features
from repo_xray.model import Route, SourceFile, Symbol
from repo_xray.pipeline import analyse
from tests.conftest import JAVA, write


@pytest.mark.parametrize(("title", "expected"), [
    ("Iniciar sesión · Benchify", "Iniciar sesión"),
    ("Benchify | Orders", "Orders"),
    ("Orders - Shop admin", "Orders - Shop admin"),
    ("Benchify", "Benchify"),
])
def test_clean_title_drops_the_project_name(title, expected):
    assert clean_title(title, "Benchify") == expected


def frontend(*features: Feature) -> FeatureMap:
    return FeatureMap(features=list(features))


def page(path: str) -> SourceFile:
    return SourceFile(path, "typescript", path.rsplit(".", 1)[0], path.rsplit("/", 1)[0], 3,
                      symbols=[Symbol("class", "Page", "x.Page", "x", 1, 3, None)])


def test_screens_come_from_route_titles_and_sentences_from_facts():
    login = Feature("web/auth", "Auth", "web", "web/src/auth", files=["web/src/auth/login-page.ts"],
                    services=["Firebase Auth"])
    orders = Feature("web/orders", "Orders", "web", "web/src/orders", files=["web/src/orders/list.ts"],
                     calls={"api/order": 3, "api/catalog": 1})
    api = Feature("api/order", "Pedidos", "api", "api/order", description="Compra de productos")
    catalog = Feature("api/catalog", "Catálogo", "api", "api/catalog", endpoints=[object()] * 2)
    router = SourceFile("web/src/app.routes.ts", "typescript", "web/src/app.routes", "web/src", 5, routes=[
        Route("login", "Iniciar sesión · Shop", "web/src/auth/login-page", 1),
        Route("pedidos", "Mis pedidos · Shop", "OrderList", 2),
    ])
    files = [router, page("web/src/auth/login-page.ts"),
             SourceFile("web/src/orders/list.ts", "typescript", "web/src/orders/list", "web/src/orders", 3,
                        symbols=[Symbol("class", "OrderList", "x.OrderList", "x", 1, 3, None)])]
    feature_map = frontend(login, orders, api, catalog)

    describe_features(feature_map, files, Stack(name="Shop"), "es")

    assert login.screens == ["Iniciar sesión"]
    assert login.description == "Pantalla: Iniciar sesión. Usa Firebase Auth."
    assert orders.description == "Pantalla: Mis pedidos. Llama a Pedidos y Catálogo."
    assert (api.description, api.description_source) == ("Compra de productos", "code")
    assert (catalog.description, catalog.description_source) == ("Expone 2 endpoints.", "generated")


def test_english_sentences_and_screens_from_file_names_without_routes():
    feature = Feature("web/cart", "Cart", "web", "web/cart",
                      files=["web/cart/cart-page.tsx", "web/cart/checkout-view.tsx", "web/cart/util.ts"],
                      layers={"entry": 2, "other": 1})

    describe_features(frontend(feature), [], Stack(name="Shop"), "en")

    assert feature.screens == ["Cart", "Checkout"]
    assert feature.description == "Screens: Cart and Checkout."


def test_last_resort_sentence_describes_files_and_layers():
    feature = Feature("lib/core", "Core", "lib", "lib/core", files=["a.py", "b.py"],
                      layers={"domain": 1, "data": 1})

    describe_features(frontend(feature), [], Stack(name="Lib"), "en")

    assert feature.description == "2 files of domain model and data access."


def test_pipeline_fills_texts_for_an_angular_frontend(tmp_path):
    write(tmp_path, {
        "package.json": '{"name": "App", "private": true}',
        "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0"}}',
        "web/src/app/app.routes.ts": """\
            export const routes: Routes = [
              { path: 'pedidos', title: 'My orders · App', loadComponent: () => import('./features/orders/orders-page').then(m => m.OrdersPage) },
            ];
        """,
        "web/src/app/features/orders/orders-page.ts": "@Component({ selector: 'x' })\nexport class OrdersPage {}\n",
        "web/src/app/features/home/home-page.ts": "@Component({ selector: 'y' })\nexport class HomePage {}\n",
    })

    features = {f.key: f for f in analyse(tmp_path).features.features}

    assert features["web/orders"].screens == ["My orders"]
    assert features["web/orders"].description == "Screen: My orders."
    assert features["web/home"].description == "Screen: Home."


def test_user_texts_win_and_choose_the_language(tmp_path):
    write(tmp_path, {
        "package.json": '{"name": "App", "private": true}',
        "web/package.json": '{"dependencies": {"@angular/core": "^19.0.0"}}',
        "web/src/app/features/orders/orders-page.ts": "@Component({ selector: 'x' })\nexport class OrdersPage {}\n",
        "web/src/app/features/home/home-page.ts": "@Component({ selector: 'y' })\nexport class HomePage {}\n",
        "xray.toml": 'language = "es"\ndescription = "Tienda de prueba"\n\n'
                     '[features."web/orders"]\nname = "Pedidos"\ndescription = "Historial de compras"\n',
    })

    analysis = analyse(tmp_path)

    features = {f.key: f for f in analysis.features.features}
    assert (analysis.language, analysis.detected_language) == ("es", "en")
    assert analysis.stack.description == "Tienda de prueba"
    assert (features["web/orders"].name, features["web/orders"].description_source) == ("Pedidos", "user")
    assert features["web/orders"].description == "Historial de compras"
    assert features["web/home"].description == "Pantalla: Home."  # generated, in the chosen language
