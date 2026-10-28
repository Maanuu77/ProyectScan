import pytest

from repo_xray.analysis.layers import LAYERS, classify
from repo_xray.model import Endpoint, HttpCall, SourceFile, Symbol


def source(path: str, decorators: list[str] | None = None, language: str | None = None, **extra) -> SourceFile:
    language = language or ("java" if path.endswith(".java") else "typescript" if ".ts" in path else "python")
    symbols = [Symbol("class", "X", "x.X", "x", 1, 2, None, decorators=decorators or [])]
    return SourceFile(path=path, language=language, name="x", package="x", line_count=2, symbols=symbols, **extra)


@pytest.mark.parametrize(("path", "expected"), [
    # Hexagonal Spring backend, as in Benchify
    ("src/main/java/shop/order/infrastructure/web/OrderController.java", "entry"),
    ("src/main/java/shop/order/infrastructure/web/dto/OrderResponse.java", "entry"),
    ("src/main/java/shop/order/application/port/in/PlaceOrderUseCase.java", "application"),
    ("src/main/java/shop/order/application/port/out/OrderRepository.java", "application"),
    ("src/main/java/shop/order/application/service/OrderService.java", "application"),
    ("src/main/java/shop/order/domain/Order.java", "domain"),
    ("src/main/java/shop/order/infrastructure/persistence/OrderJpaRepository.java", "data"),
    ("src/main/java/shop/shared/infrastructure/security/TokenFilter.java", "integration"),
    ("src/main/java/shop/order/infrastructure/storage/StorageConfig.java", "integration"),
    # Layer-first projects
    ("src/main/java/shop/controllers/CartController.java", "entry"),
    ("src/main/java/shop/services/CartService.java", "application"),
    ("src/main/java/shop/repositories/CartRepository.java", "data"),
    ("app/models.py", "domain"),
    # Frontends
    ("src/app/core/api/models.ts", "domain"),
    ("src/app/core/auth/auth.interceptor.ts", "integration"),
    ("src/app/app.config.ts", "integration"),
    ("src/app/features/admin/admin.routes.ts", "entry"),
    ("src/hooks/useCart.ts", "application"),
    ("src/store/cart-store.ts", "application"),
    # Tests and leftovers
    ("src/test/java/shop/OrderServiceTest.java", "test"),
    ("src/app/cart.spec.ts", "test"),
    ("scripts/tool.py", "other"),
])
def test_layer_from_path_and_name(path, expected):
    assert classify(source(path)) == expected


def test_api_folder_depends_on_the_kind_of_app():
    assert classify(source("src/app/api/helpers.ts"), app_kind="web") == "data"
    assert classify(source("src/main/java/shop/api/Helpers.java"), app_kind="api") == "entry"


def test_code_evidence_beats_folder_names():
    endpoint = Endpoint("GET", "/orders", "x.X.all", 1)
    request = HttpCall("GET", "/api/orders", "x.X.load", 1)

    assert classify(source("src/domain/Weird.java", endpoints=[endpoint])) == "entry"
    assert classify(source("src/app/shared/orders.ts", http_calls=[request])) == "data"
    assert classify(source("src/main/java/shop/domain/OrderRow.java", ["Entity", "Table(name = \"orders\")"])) == "data"
    assert classify(source("src/app/shared/badge.ts", ["Component({ selector: 'x' })"])) == "entry"


def test_spring_component_annotation_does_not_mean_ui():
    path = "src/main/java/shop/order/infrastructure/persistence/OrderPersistenceAdapter.java"

    assert classify(source(path, ["Component"])) == "data"


def test_every_layer_has_a_label():
    assert set(LAYERS) == {"entry", "application", "domain", "data", "integration", "test", "other"}
