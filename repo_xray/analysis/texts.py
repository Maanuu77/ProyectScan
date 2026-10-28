"""Words for features that the code does not describe (ADR-0011).

Screens get the titles their routes declare ("Iniciar sesión · Benchify"
becomes "Iniciar sesión"). A feature with no description of its own gets
a sentence built only from facts the analysis found, so it is always true:
"Pantallas: Iniciar sesión y Crear cuenta. Usa Firebase Auth."
"""

import posixpath
import re

from repo_xray import i18n
from repo_xray.analysis.features import Feature, FeatureMap
from repo_xray.analysis.stack import Stack
from repo_xray.model import Route, SourceFile

DRAWN_LAYERS = ("entry", "application", "domain", "data", "integration")
MAX_SCREENS = 5
_SEPARATORS = re.compile(r"\s+[·|\-–—:]\s+")
_SCREEN_SUFFIX = re.compile(r"[-_.]?(page|component|view|screen|container)$", re.IGNORECASE)

TEXTS = {
    "screen": {"en": "Screen: {names}.", "es": "Pantalla: {names}."},
    "screens": {"en": "Screens: {names}.", "es": "Pantallas: {names}."},
    "calls": {"en": "Calls {names}.", "es": "Llama a {names}."},
    "uses": {"en": "Uses {names}.", "es": "Usa {names}."},
    "depends": {"en": "Depends on {names}.", "es": "Depende de {names}."},
    "exposes": {"en": "Exposes {endpoints}.", "es": "Expone {endpoints}."},
    "files": {"en": "{files} of {layers}.", "es": "{files} de {layers}."},
}


def describe_features(feature_map: FeatureMap, files: list[SourceFile], stack: Stack, lang: str) -> None:
    """Fill `screens` and, when the code gives none, a generated `description` for every feature."""
    owners = {path: feature for feature in feature_map.features for path in feature.files}
    by_module = {_without_extension(f.path): f.path for f in files}
    by_class = {s.name: f.path for f in files for s in f.symbols if s.kind == "class"}
    for file in files:
        for route in file.routes:
            path = by_module.get(route.target) or by_module.get(route.target + "/index") or by_class.get(route.target)
            feature = owners.get(path) if path else None
            name = _screen_name(route, path, stack.name)
            if feature is not None and name and name not in feature.screens:
                feature.screens.append(name)
    names = {f.key: f.name for f in feature_map.features}
    for feature in feature_map.features:
        if not feature.screens:
            feature.screens = _screens_from_files(feature)
        if not feature.description:
            feature.description = _sentence(feature, names, lang)
            feature.description_source = "generated"


def clean_title(title: str, project: str) -> str:
    """`Iniciar sesión · Benchify` -> `Iniciar sesión`: the app's own name says nothing here."""
    parts = [p.strip() for p in _SEPARATORS.split(title.strip())]
    kept = [p for p in parts if p and p.casefold() != project.casefold()]
    if not kept or len(kept) == len(parts):
        return title.strip()  # nothing to drop: keep the title exactly as written
    return " · ".join(kept)


def _screen_name(route: Route, path: str | None, project: str) -> str | None:
    if route.title:
        return clean_title(route.title, project)
    if path and _SCREEN_SUFFIX.search(posixpath.basename(path).split(".")[0]):
        return _humanize(posixpath.basename(path).split(".")[0])
    return None


def _screens_from_files(feature: Feature) -> list[str]:
    stems = [posixpath.basename(p).split(".")[0] for p in feature.files]
    return list(dict.fromkeys(_humanize(s) for s in stems if _SCREEN_SUFFIX.search(s)))


def _humanize(stem: str) -> str:
    words = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", _SCREEN_SUFFIX.sub("", stem).replace("-", " ").replace("_", " "))
    text = " ".join(w.lower() for w in words)
    return text[:1].upper() + text[1:]


def _sentence(feature: Feature, names: dict[str, str], lang: str) -> str:
    def say(key: str, **values) -> str:
        return TEXTS[key].get(lang, TEXTS[key][i18n.DEFAULT]).format(**values)

    parts = []
    if feature.screens:
        shown = feature.screens[:MAX_SCREENS]
        listed = i18n.join(lang, shown) + ("…" if len(feature.screens) > MAX_SCREENS else "")
        parts.append(say("screen" if len(feature.screens) == 1 else "screens", names=listed))
    elif feature.endpoints:
        parts.append(say("exposes", endpoints=i18n.count(lang, len(feature.endpoints), "endpoint")))
    if feature.calls:
        parts.append(say("calls", names=i18n.join(lang, [names[k] for k in _ranked(feature.calls)])))
    elif feature.depends_on:
        parts.append(say("depends", names=i18n.join(lang, [names[k] for k in _ranked(feature.depends_on)])))
    if feature.services:
        parts.append(say("uses", names=i18n.join(lang, feature.services)))
    if not parts:
        layers = [i18n.text(lang, f"layer.{layer}").lower() for layer in DRAWN_LAYERS if feature.layers.get(layer)]
        files = i18n.count(lang, len(feature.files), "file")
        parts.append(say("files", files=files, layers=i18n.join(lang, layers)) if layers else files + ".")
    return " ".join(parts)


def _ranked(counts: dict[str, int]) -> list[str]:
    return sorted(counts, key=lambda key: -counts[key])


def _without_extension(path: str) -> str:
    return path.rsplit(".", 1)[0]
