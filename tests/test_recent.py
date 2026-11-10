import pytest
from PySide6.QtCore import QSettings

from repo_xray.app.recent import MAX_RECENT, RecentProject, RecentProjects, ago


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def folders(tmp_path, count):
    made = [tmp_path / f"p{i}" for i in range(count)]
    for folder in made:
        folder.mkdir()
    return made


def test_the_latest_comes_first_without_duplicates(settings, tmp_path):
    recent = RecentProjects(settings)
    made = folders(tmp_path, MAX_RECENT + 2)
    for folder in made:
        recent.remember(folder)
    recent.remember(made[3])

    paths = [project.path for project in recent.all()]

    assert paths[0] == str(made[3])
    assert len(paths) == MAX_RECENT == len(set(paths))


def test_what_the_analysis_found_is_remembered(settings, tmp_path):
    folder = folders(tmp_path, 1)[0]
    RecentProjects(settings).remember(folder, "Benchify", apps=2, features=15, flows=63)

    project = RecentProjects(settings).all()[0]  # a new session reads the same settings

    assert project.title == "Benchify" and project.exists
    assert project.summary() == "2 apps  ·  15 features  ·  63 flows"
    assert project.opened > 0


def test_summary_says_only_what_there_is():
    assert RecentProject("x", apps=1, features=1).summary() == "1 app  ·  1 feature"
    assert RecentProject("x").summary() == ""
    assert RecentProject("C:/code/shop").title == "shop"  # the folder's name when the project has none


def test_folders_that_are_gone_are_not_offered(settings, tmp_path):
    recent = RecentProjects(settings)
    kept, gone = folders(tmp_path, 2)
    recent.remember(gone)
    recent.remember(kept)
    gone.rmdir()

    assert [project.path for project in recent.all()] == [str(kept)]


def test_forget_and_clear(settings, tmp_path):
    recent = RecentProjects(settings)
    first, second = folders(tmp_path, 2)
    recent.remember(first, "one")
    recent.remember(second, "two")

    recent.forget(second)
    assert [project.title for project in recent.all()] == ["one"]
    recent.clear()
    assert recent.all() == []


def test_the_list_of_version_1_is_still_read(settings, tmp_path):
    folder = folders(tmp_path, 1)[0]
    settings.setValue("recent", [str(folder)])  # 1.0 stored only the paths

    project = RecentProjects(settings).all()[0]

    assert project.path == str(folder) and project.title == folder.name and project.summary() == ""


def test_damaged_details_only_lose_the_details(settings, tmp_path):
    folder = folders(tmp_path, 1)[0]
    RecentProjects(settings).remember(folder, "shop", apps=1)
    settings.setValue("recent_details", "{not json")

    project = RecentProjects(settings).all()[0]

    assert project.path == str(folder) and project.apps == 0


@pytest.mark.parametrize("seconds, expected", [
    (5, "just now"), (60 * 5, "5 minutes ago"), (3600 * 3, "3 hours ago"), (86400, "yesterday"),
    (86400 * 3, "3 days ago"), (86400 * 14, "2 weeks ago"), (86400 * 90, "3 months ago"), (86400 * 800, "2 years ago"),
])
def test_how_long_ago(seconds, expected):
    now = 1_000_000_000.0

    assert ago(now - seconds, now) == expected


def test_an_unknown_moment_says_nothing():
    assert ago(0) == ""
