import pytest

from repo_xray.pipeline import STAGES, Cancelled, Progress, analyse
from tests.conftest import hexagonal_backend


def test_progress_reports_every_stage_in_order(tmp_path):
    hexagonal_backend(tmp_path)
    seen: list[Progress] = []

    analysis = analyse(tmp_path, seen.append)

    stages = list(dict.fromkeys(p.stage for p in seen))
    assert stages == list(STAGES)
    assert analysis.seconds > 0


def test_parsing_counts_real_files_never_a_made_up_fraction(tmp_path):
    hexagonal_backend(tmp_path)
    seen: list[Progress] = []

    analysis = analyse(tmp_path, seen.append)

    parsing = [p for p in seen if p.stage == "parse"]
    assert parsing[0].done == 0 and parsing[0].detail.endswith(".java")
    assert parsing[-1].done == parsing[-1].total == len(analysis.files)
    assert all(p.total == 0 for p in seen if p.stage != "parse")  # nothing to count: no number shown


def test_progress_has_words_for_each_stage():
    assert Progress("parse").label == "Reading the code"
    assert Progress("render").label == "render"  # stages added by callers bring their own words


def test_cancelling_stops_at_the_next_checkpoint(tmp_path):
    hexagonal_backend(tmp_path)
    seen: list[Progress] = []

    with pytest.raises(Cancelled):
        analyse(tmp_path, seen.append, cancelled=lambda: len(seen) >= 2)

    assert [p.stage for p in seen] == ["scan", "parse"]  # stopped before any later stage


def test_cancelled_before_it_starts_does_no_work(tmp_path):
    with pytest.raises(Cancelled):
        analyse(tmp_path / "missing", cancelled=lambda: True)  # would fail on the folder otherwise
