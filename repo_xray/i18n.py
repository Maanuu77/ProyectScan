"""Every fixed text of the documents, in English and Spanish.

Names and descriptions come from the analysed code, so the labels around
them follow the language of that code (ADR-0011): a Spanish project is
documented in Spanish and an English one in English, without mixing.
"""

import re
from collections.abc import Iterable

LANGUAGES = ("en", "es")
DEFAULT = "en"

TEXTS: dict[str, dict[str, str]] = {
    # Kinds of app, as card labels and inside sentences
    "kind.web": {"en": "WEB APP", "es": "APLICACIÓN WEB"},
    "kind.api": {"en": "API", "es": "API"},
    "kind.mobile": {"en": "MOBILE APP", "es": "APP MÓVIL"},
    "kind.desktop": {"en": "DESKTOP APP", "es": "APP DE ESCRITORIO"},
    "kind.library": {"en": "APPLICATION", "es": "APLICACIÓN"},
    "kind_name.web": {"en": "web app", "es": "aplicación web"},
    "kind_name.api": {"en": "API", "es": "API"},
    "kind_name.mobile": {"en": "mobile app", "es": "app móvil"},
    "kind_name.desktop": {"en": "desktop app", "es": "app de escritorio"},
    "kind_name.library": {"en": "application", "es": "aplicación"},
    "kind_title.web": {"en": "Web app", "es": "Aplicación web"},
    "kind_title.api": {"en": "API", "es": "API"},
    "kind_title.mobile": {"en": "Mobile app", "es": "App móvil"},
    "kind_title.desktop": {"en": "Desktop app", "es": "App de escritorio"},
    "kind_title.library": {"en": "Application", "es": "Aplicación"},
    # Service categories and what apps do with them
    "category.database": {"en": "Database", "es": "Base de datos"},
    "category.auth": {"en": "Authentication", "es": "Autenticación"},
    "category.storage": {"en": "File storage", "es": "Almacenamiento de archivos"},
    "category.cache": {"en": "Cache", "es": "Caché"},
    "category.messaging": {"en": "Messaging", "es": "Mensajería"},
    "category.search": {"en": "Search", "es": "Búsqueda"},
    "category.platform": {"en": "Platform", "es": "Plataforma"},
    "category.external": {"en": "External API", "es": "API externa"},
    "category.other": {"en": "Service", "es": "Servicio"},
    "verb.database": {"en": "reads & writes", "es": "lee y escribe"},
    "verb.auth": {"en": "verifies users", "es": "verifica usuarios"},
    "verb.storage": {"en": "stores files", "es": "guarda archivos"},
    "verb.cache": {"en": "caches", "es": "cachea"},
    "verb.messaging": {"en": "publishes events", "es": "publica eventos"},
    "verb.search": {"en": "indexes", "es": "indexa"},
    "verb.platform": {"en": "uses", "es": "usa"},
    "verb.external": {"en": "calls", "es": "llama"},
    "verb.client.auth": {"en": "signs in", "es": "inicia sesión"},
    "verb.client.storage": {"en": "uploads files", "es": "sube archivos"},
    # Layers
    "layer.entry": {"en": "Entry points", "es": "Puntos de entrada"},
    "layer.application": {"en": "Application logic", "es": "Lógica de aplicación"},
    "layer.domain": {"en": "Domain model", "es": "Modelo de dominio"},
    "layer.data": {"en": "Data access", "es": "Acceso a datos"},
    "layer.integration": {"en": "Integrations & config", "es": "Integraciones y configuración"},
    "layer.test": {"en": "Tests", "es": "Pruebas"},
    "layer.other": {"en": "Other", "es": "Otros"},
    "step.entry": {"en": "ENTRY POINT", "es": "PUNTO DE ENTRADA"},
    "step.application": {"en": "APPLICATION LOGIC", "es": "LÓGICA DE APLICACIÓN"},
    "step.domain": {"en": "DOMAIN", "es": "DOMINIO"},
    "step.data": {"en": "DATA ACCESS", "es": "ACCESO A DATOS"},
    "step.integration": {"en": "INTEGRATION", "es": "INTEGRACIÓN"},
    "step.other": {"en": "CODE", "es": "CÓDIGO"},
    # Level 1
    "overview": {"en": "Architecture overview", "es": "Visión general de la arquitectura"},
    "users": {"en": "Users", "es": "Usuarios"},
    "rest": {"en": "REST", "es": "REST"},
    "generated": {"en": "Generated with repo-xray", "es": "Generado con repo-xray"},
    "overview.description": {"en": "{name} is made of {apps}. It uses {services}.",
                             "es": "{name} está formado por {apps}. Usa {services}."},
    "no_services": {"en": "no external services", "es": "ningún servicio externo"},
    # Level 2
    "features.subtitle": {"en": "Features  ·  What does it do?", "es": "Funcionalidades  ·  ¿Qué hace?"},
    "in_apps": {"en": "in {n} apps", "es": "en {n} aplicaciones"},
    "shared_code": {"en": "Shared code:", "es": "Código compartido:"},
    "chip.calls": {"en": "CALLS", "es": "LLAMA A"},
    "chip.uses": {"en": "USES", "es": "USA"},
    "more_features": {"en": "+ {n} more features", "es": "+ {n} funcionalidades más"},
    "features.description": {"en": "Features of {name}.", "es": "Funcionalidades de {name}."},
    "fallback.screens": {"en": "Screens: {names}", "es": "Pantallas: {names}"},
    "fallback.layers": {"en": "{files} across {layers}", "es": "{files} en {layers}"},
    # Level 3
    "flow.kicker": {"en": "WHAT HAPPENS WHEN…", "es": "QUÉ PASA CUANDO…"},
    "flow.title": {"en": "What happens when: {title}", "es": "Qué pasa cuando: {title}"},
    "flow.data_lane": {"en": "Data & services", "es": "Datos y servicios"},
    "flow.stores": {"en": "STORES THE RESULT", "es": "GUARDA EL RESULTADO"},
    "flow.footer": {"en": "Main path only: helpers, mappers and validations are left out.",
                    "es": "Solo el camino principal: se omiten utilidades, mappers y validaciones."},
    # Pages
    "page.title": {"en": "{name} architecture", "es": "Arquitectura de {name}"},
    "page.made_of": {"en": "What is it made of?", "es": "¿De qué está hecho?"},
    "page.does": {"en": "What does it do?", "es": "¿Qué hace?"},
    "page.happens": {"en": "What happens when…?", "es": "¿Qué pasa cuando…?"},
    "page.alt_overview": {"en": "{name} overview", "es": "Visión general de {name}"},
    "page.alt_features": {"en": "{name} features", "es": "Funcionalidades de {name}"},
    "page.footer": {"en": "_Generated with repo-xray from the source code. "
                          "Diagrams show the main structure; small helpers are left out._",
                    "es": "_Generado con repo-xray a partir del código fuente. "
                          "Los diagramas muestran la estructura principal; se omiten los detalles menores._"},
    "page.part_of": {"en": "Part of **{app}** ({kind}) · {where} · [back to the overview](../README.md)",
                     "es": "Parte de **{app}** ({kind}) · {where} · [volver a la visión general](../README.md)"},
    "page.grouped_by_name": {"en": "files grouped by name", "es": "archivos agrupados por nombre"},
    "page.layers": {"en": "Layers", "es": "Capas"},
    "page.layer_table": {"en": "| Layer | Files |", "es": "| Capa | Archivos |"},
    "page.endpoints": {"en": "Endpoints", "es": "Endpoints"},
    "page.endpoint_table": {"en": "| Method | Route | What it does |", "es": "| Método | Ruta | Qué hace |"},
    "page.connections": {"en": "Connections", "es": "Conexiones"},
    "page.calls": {"en": "Calls", "es": "Llama a"},
    "page.called_from": {"en": "Called from", "es": "Llamado desde"},
    "page.depends_on": {"en": "Depends on", "es": "Depende de"},
    "page.used_by": {"en": "Used by", "es": "Usado por"},
    "page.services": {"en": "Services", "es": "Servicios"},
    "page.files": {"en": "Files", "es": "Archivos"},
    # Summary paragraph
    "summary.made_of": {"en": "{name} is made of {apps}.", "es": "{name} está formado por {apps}."},
    "summary.app": {"en": "{article} {kind} (`{app}`)", "es": "una {kind} (`{app}`)"},
    "summary.built_with": {"en": " built with {techs}", "es": " hecha con {techs}"},
    "summary.no_app": {"en": "{name} has no recognisable app yet.", "es": "{name} todavía no tiene ninguna aplicación reconocible."},
    "summary.stores": {"en": " It stores its data in {stores}", "es": " Guarda sus datos en {stores}"},
    "summary.and_relies": {"en": " and relies on {others}.", "es": " y usa {others}."},
    "summary.relies": {"en": " It relies on {others}.", "es": " Usa {others}."},
    "summary.features": {"en": " The code is organised in {n} features, described below.",
                         "es": " El código se organiza en {n} funcionalidades, descritas abajo."},
    "and": {"en": "and", "es": "y"},
}

# Counted words: (singular, plural) templates.
COUNTS: dict[str, dict[str, tuple[str, str]]] = {
    "app": {"en": ("{n} app", "{n} apps"), "es": ("{n} aplicación", "{n} aplicaciones")},
    "service": {"en": ("{n} service", "{n} services"), "es": ("{n} servicio", "{n} servicios")},
    "file": {"en": ("{n} file", "{n} files"), "es": ("{n} archivo", "{n} archivos")},
    "lines": {"en": ("{n} line", "{n} lines"), "es": ("{n} línea", "{n} líneas")},
    "lines_of_code": {"en": ("{n} line of code", "{n} lines of code"),
                      "es": ("{n} línea de código", "{n} líneas de código")},
    "endpoint": {"en": ("{n} endpoint", "{n} endpoints"), "es": ("{n} endpoint", "{n} endpoints")},
    "feature": {"en": ("{n} feature", "{n} features"), "es": ("{n} funcionalidad", "{n} funcionalidades")},
    "call": {"en": ("{n} call", "{n} calls"), "es": ("{n} llamada", "{n} llamadas")},
}

_SPANISH = {"de", "y", "la", "el", "los", "las", "que", "por", "para", "una", "con", "del", "se", "su", "sus",
            "es", "al", "como", "pero", "más", "cuando", "si", "ya", "este", "esta", "sin", "sobre"}
_ENGLISH = {"the", "of", "and", "to", "is", "for", "with", "that", "this", "from", "are", "be", "it",
            "an", "by", "on", "as", "when", "if", "not", "or", "which", "should", "returns"}
_WORD = re.compile(r"[a-záéíóúñü]+")


def text(lang: str, key: str, **values) -> str:
    entry = TEXTS[key]
    return entry.get(lang, entry[DEFAULT]).format(**values)


def count(lang: str, n: int, key: str, number: str | None = None) -> str:
    """`count("es", 3, "file")` -> "3 archivos"; `number` overrides how n is written (e.g. "15.6k")."""
    forms = COUNTS[key].get(lang, COUNTS[key][DEFAULT])
    return forms[0 if n == 1 else 1].format(n=number if number is not None else n)


def join(lang: str, items: list[str]) -> str:
    items = [item for item in items if item]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {text(lang, 'and')} " + items[-1]


def detect_language(texts: Iterable[str | None]) -> str:
    """Spanish or English, from comments, descriptions and other prose found in the project."""
    spanish = english = 0
    for item in texts:
        for word in _WORD.findall((item or "").lower()):
            spanish += word in _SPANISH or any(c in word for c in "áéíóúñ")
            english += word in _ENGLISH
    return "es" if spanish >= 5 and spanish > english * 1.2 else DEFAULT
