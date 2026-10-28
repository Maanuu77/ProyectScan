import pytest

from repo_xray import i18n
from repo_xray.export.markdown import FOLDER, build_documents
from repo_xray.pipeline import analyse
from tests.conftest import JAVA, write


def test_every_text_exists_in_every_language():
    for key, entry in i18n.TEXTS.items():
        assert set(entry) == set(i18n.LANGUAGES), key
    for key, entry in i18n.COUNTS.items():
        assert set(entry) == set(i18n.LANGUAGES), key


def test_texts_counts_and_lists():
    assert i18n.text("es", "users") == "Usuarios"
    assert i18n.text("fr", "users") == "Users"  # unknown languages fall back to English
    assert i18n.count("en", 1, "file") == "1 file"
    assert i18n.count("es", 3, "file") == "3 archivos"
    assert i18n.count("en", 15600, "lines", "15.6k") == "15.6k lines"
    assert i18n.join("es", ["a", "b", "c"]) == "a, b y c"
    assert i18n.join("en", ["a"]) == "a"


@pytest.mark.parametrize(("texts", "expected"), [
    (["Valoraciones de bancos y reportes de contenido inapropiado", "Perfil propio y perfiles públicos"], "es"),
    (["Returns the orders of the current user", "Saves the cart and sends the receipt"], "en"),
    (["Crea un pedido"], "en"),  # too little evidence: English is the default
    ([None, ""], "en"),
])
def test_language_detection(texts, expected):
    assert i18n.detect_language(texts) == expected


def test_a_spanish_project_is_documented_in_spanish(tmp_path):
    write(tmp_path, {
        "api/pom.xml": "<project><dependencies><dependency><artifactId>spring-boot-starter-web</artifactId>"
                       "</dependency></dependencies></project>",
        f"api/{JAVA}/pedido/infrastructure/web/PedidoController.java": """\
            package shop.pedido.infrastructure.web;
            /** Gestiona los pedidos de la tienda y el historial de compras de cada cliente. */
            @RestController
            @Tag(name = "Pedidos", description = "Compra de productos y consulta de los pedidos del cliente")
            class PedidoController {
                @PostMapping("/api/pedidos") @Operation(summary = "Crear un pedido con los productos del carrito")
                Object crear() { return null; }
            }
        """,
        f"api/{JAVA}/pedido/domain/Pedido.java": "package shop.pedido.domain;\nrecord Pedido(String id) {}\n",
    })

    analysis = analyse(tmp_path)
    bundle = build_documents(analysis)

    assert analysis.language == "es"
    index = bundle[f"{FOLDER}/README.md"]
    assert index.startswith(f"# Arquitectura de {tmp_path.name}\n\n{tmp_path.name} está formado por una API (`api`)")
    assert "## ¿De qué está hecho?" in index
    assert "Usuarios" in bundle[f"{FOLDER}/images/overview-light.svg"]
