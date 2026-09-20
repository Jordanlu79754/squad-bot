"""Tests for patch-note extraction and the seen-state that drives announcements."""

import pytest

from features import patchnotes as pn
from features.state import State

LOL_HTML = """
<html><body>
<a href="/en-us/news/game-updates/league-of-legends-patch-26-10-notes">x</a>
<a href="/en-us/news/game-updates/league-of-legends-patch-26-12-notes">x</a>
<a href="/en-us/news/game-updates/league-of-legends-patch-26-9-notes">x</a>
<a href="/en-us/news/game-updates/league-of-legends-patch-26-12-notes">duplicate</a>
<a href="/en-us/news/media/some-cinematic">unrelated</a>
<a href="https://example.com/en-us/news/game-updates/other-patch">offsite</a>
</body></html>
"""


def test_extracts_only_patch_links():
    notes = pn.parse_listing("lol", LOL_HTML)

    assert len(notes) == 3
    assert all("patch" in note.url for note in notes)


def test_duplicate_links_collapse():
    urls = [note.url for note in pn.parse_listing("lol", LOL_HTML)]

    assert len(urls) == len(set(urls))


def test_versions_are_parsed_and_sorted_newest_first():
    versions = [note.version for note in pn.parse_listing("lol", LOL_HTML)]

    assert versions == ["26.12", "26.10", "26.9"]


def test_urls_are_absolute():
    note = pn.parse_listing("lol", LOL_HTML)[0]

    assert note.url.startswith("https://www.leagueoflegends.com/")


def test_title_reads_like_a_human_wrote_it():
    assert pn.parse_listing("lol", LOL_HTML)[0].title == "League of Legends patch 26.12"


def test_valorant_slug_shape():
    html = '<a href="/en-us/news/game-updates/valorant-patch-notes-12-07">x</a>'
    note = pn.parse_listing("valorant", html)[0]

    assert note.version == "12.07"
    assert note.title == "VALORANT patch 12.07"


def test_tft_slug_shape():
    html = '<a href="/en-us/news/game-updates/teamfight-tactics-patch-17-2">x</a>'
    note = pn.parse_listing("tft", html)[0]

    assert note.version == "17.2"
    assert note.game_name == "Teamfight Tactics"


def test_unparseable_version_still_yields_a_usable_note():
    html = '<a href="/en-us/news/game-updates/a-special-patch-update">x</a>'
    note = pn.parse_listing("lol", html)[0]

    assert note.version == ""
    assert note.title == "League of Legends patch notes"


def test_empty_page_yields_nothing():
    assert pn.parse_listing("lol", "<html></html>") == []


@pytest.mark.parametrize("name,expected", [
    ("lol", "lol"), ("LoL", "lol"), ("league", "lol"),
    (" tft ", "tft"), ("val", "valorant"), ("VALORANT", "valorant"),
])
def test_game_aliases(name, expected):
    assert pn.resolve_game(name) == expected


def test_unknown_game_is_rejected():
    assert pn.resolve_game("dota") is None


# ---------------------------------------------------------------------- state


def test_seen_state_survives_a_restart(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    state.mark_patch_seen("lol", "https://example.com/patch-1")
    state.save()

    reloaded = State(path)

    assert reloaded.is_patch_seen("lol", "https://example.com/patch-1")
    assert not reloaded.is_patch_seen("tft", "https://example.com/patch-1")


def test_first_run_is_distinguishable_from_nothing_new(tmp_path):
    state = State(tmp_path / "state.json")

    assert not state.has_seen_any("lol")
    state.mark_patch_seen("lol", "https://example.com/patch-1")
    assert state.has_seen_any("lol")


def test_corrupt_state_file_does_not_stop_the_bot(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ this is not json", encoding="utf-8")

    state = State(path)

    assert not state.has_seen_any("lol")
    state.mark_patch_seen("lol", "https://example.com/p")
    state.save()
    assert State(path).is_patch_seen("lol", "https://example.com/p")


def test_seen_list_is_bounded(tmp_path):
    state = State(tmp_path / "state.json")
    for index in range(100):
        state.mark_patch_seen("lol", f"https://example.com/patch-{index}")

    assert len(state._data["seen_patches"]["lol"]) == 40
    assert state.is_patch_seen("lol", "https://example.com/patch-99")


def test_rate_needs_two_samples(tmp_path):
    state = State(tmp_path / "state.json")
    state.record_order_sample(1, [100])

    assert state.progress_rate(1, 0) is None


def test_rate_ignores_samples_taken_too_close_together(tmp_path):
    state = State(tmp_path / "state.json")
    # Written directly so the timestamps are controlled; a rate measured over
    # five minutes is noise, not a trend.
    state._data["order_samples"]["1"] = [
        ["2026-09-20T00:00:00+00:00", [0]],
        ["2026-09-20T00:05:00+00:00", [500]],
    ]

    assert state.progress_rate(1, 0) is None


def test_rate_is_progress_per_second(tmp_path):
    state = State(tmp_path / "state.json")
    state._data["order_samples"]["1"] = [
        ["2026-09-20T00:00:00+00:00", [0]],
        ["2026-09-20T01:00:00+00:00", [3600]],
    ]

    assert state.progress_rate(1, 0) == pytest.approx(1.0)


def test_starting_a_new_order_discards_the_old_history(tmp_path):
    state = State(tmp_path / "state.json")
    state.record_order_sample(1, [100])
    state.record_order_sample(2, [0])

    assert "1" not in state._data["order_samples"]
    assert "2" in state._data["order_samples"]
