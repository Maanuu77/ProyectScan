"""Names for the parts of a diagram that stand for something in the project.

Cards carry an `id` such as `feature-backend-resena`. SVG ignores it when
drawing, so GitHub and browsers show the same picture, but the desktop app
can ask where the element is and take the reader to that feature's page
when they click it.
"""

import re
import unicodedata

APP, SERVICE, FEATURE, STEP = "app", "service", "feature", "step"
_ID = re.compile(r"^(app|service|feature)-(.+)$|^step-(\d+)-(.*)$")


def slug(text: str) -> str:
    """`backend/Reseñas` -> `backend-resenas`: safe in a file name, a URL and an XML id."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "x"


def app_id(name: str) -> str:
    return f"{APP}-{slug(name)}"


def service_id(name: str) -> str:
    return f"{SERVICE}-{slug(name)}"


def feature_id(key: str) -> str:
    return f"{FEATURE}-{slug(key)}"


def step_id(number: int, feature_key: str | None) -> str:
    """A step of a flow; it leads to the feature its code belongs to, when there is one."""
    return f"{STEP}-{number}-{slug(feature_key) if feature_key else ''}"


def parse(element_id: str) -> tuple[str, str] | None:
    """(kind, slug) of an id made here: `step-3-backend-resena` -> ("feature", "backend-resena").

    A step answers with the feature it belongs to, because that is where a click leads.
    Returns None for ids that are not ours or that lead nowhere.
    """
    match = _ID.match(element_id)
    if match is None:
        return None
    if match.group(1):
        return match.group(1), match.group(2)
    return (FEATURE, match.group(4)) if match.group(4) else None
