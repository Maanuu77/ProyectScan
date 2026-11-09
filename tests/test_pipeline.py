import pytest

from repo_xray.parsers.cache import ParseCache
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


def test_a_second_analysis_reads_only_what_changed(tmp_path):
    hexagonal_backend(tmp_path)
    cache = ParseCache()

    first = analyse(tmp_path, cache=cache)
    assert cache.hits == 0 and cache.misses == len(first.files) == len(cache)

    second = analyse(tmp_path, cache=cache)
    assert cache.hits == len(first.files)
    assert [f.path for f in second.files] == [f.path for f in first.files]
    assert all(a is b for a, b in zip(first.files, second.files))  # the same parsed objects, not copies

    changed = tmp_path / "api/src/main/java/shop/order/domain/Order.java"
    changed.write_text("package shop.order.domain;\nrecord Order(String id, int total) {}\n", encoding="utf-8")
    third = analyse(tmp_path, cache=cache)
    reparsed = [a.path for a, b in zip(third.files, first.files) if a is not b]
    assert reparsed == ["api/src/main/java/shop/order/domain/Order.java"]


def test_cached_and_fresh_analyses_agree(tmp_path):
    hexagonal_backend(tmp_path)
    cache = ParseCache()
    analyse(tmp_path, cache=cache)

    cached, fresh = analyse(tmp_path, cache=cache), analyse(tmp_path)

    assert [f.key for f in cached.features.features] == [f.key for f in fresh.features.features]
    assert [f.key for f in cached.flows] == [f.key for f in fresh.flows]
    assert cached.stack == fresh.stack


def test_broken_files_are_not_remembered(tmp_path):
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
    cache = ParseCache()

    analysis = analyse(tmp_path, cache=cache)

    assert [f.path for f in analysis.files if f.error] == ["bad.py"]
    assert len(cache) == 1  # only the file that parsed


def test_files_keep_their_sorted_order_across_read_batches(tmp_path, monkeypatch):
    monkeypatch.setattr("repo_xray.pipeline.READ_AHEAD", 3)
    for index in range(10):
        (tmp_path / f"m{index:02}.py").write_text(f"VALUE = {index}\n", encoding="utf-8")

    analysis = analyse(tmp_path)

    assert [f.path for f in analysis.files] == [f"m{index:02}.py" for index in range(10)]
