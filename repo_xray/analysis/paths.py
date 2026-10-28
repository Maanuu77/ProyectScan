"""Path conventions shared by the analysis steps."""

import posixpath
import re

_TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|e2e|spec|testing)(/|$)"  # test folders
    r"|(^|/)src/test/"  # Maven and Gradle
    r"|\.(spec|test|e2e)\.[jt]sx?$"  # Jest, Jasmine, Vitest, Playwright
    r"|(^|/)test_[^/]*\.py$|_test\.py$"  # pytest
    r"|Tests?\.java$|IT\.java$",  # JUnit
)


def is_test_path(path: str) -> bool:
    return bool(_TEST_PATH.search(path))


def is_inside(path: str, folder: str) -> bool:
    """Whether `path` is `folder` itself or something inside it ("." is the project root)."""
    if folder in (".", ""):
        return True
    normalized = posixpath.normpath(path)
    return normalized == folder or normalized.startswith(folder + "/")
