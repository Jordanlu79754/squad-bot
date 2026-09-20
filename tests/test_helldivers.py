"""Tests for the Helldivers 2 parsing and projection logic.

All fixtures are shaped like real API responses, so none of these touch the
network.
"""

from datetime import datetime, timedelta, timezone

import pytest

from features import helldivers as hd


def kill_task(current_target_faction):
    current, target, faction = current_target_faction
    return current, {"type": 3, "values": [faction, 0, target, 0, 0, 0, 0, 0, 0, 0]}


def order_payload(tasks, expiration=None):
    """Build an /assignments response from (current, target, faction) tuples."""
    progress, task_dicts = [], []
    for spec in tasks:
        current, task = kill_task(spec)
        progress.append(current)
        task_dicts.append(task)
    return [{
        "id": 806233317,
        "title": "MAJOR ORDER",
        "briefing": "Hold the line.",
        "progress": progress,
        "tasks": task_dicts,
        "expiration": expiration,
    }]


# ----------------------------------------------------------------- major order


def test_no_active_order():
    assert hd.parse_major_order([]) is None


def test_parses_tasks_and_targets():
    order = hd.parse_major_order(order_payload([(750, 1000, 2), (500, 500, 3)]))

    assert order.id == 806233317
    assert order.briefing == "Hold the line."
    assert len(order.tasks) == 2
    assert order.tasks[0].current == 750
    assert order.tasks[0].target == 1000
    assert order.tasks[0].faction == "Terminids"
    assert order.tasks[1].faction == "Automatons"


def test_fraction_and_completion():
    order = hd.parse_major_order(order_payload([(250, 1000, 2), (500, 500, 3)]))

    assert order.tasks[0].fraction == pytest.approx(0.25)
    assert not order.tasks[0].complete
    assert order.tasks[1].complete
    assert not order.complete


def test_order_is_complete_only_when_every_task_is():
    order = hd.parse_major_order(order_payload([(10, 10, 2), (5, 5, 3)]))

    assert order.complete


def test_overshooting_the_target_caps_at_one():
    order = hd.parse_major_order(order_payload([(9_000, 1_000, 2)]))

    assert order.tasks[0].fraction == 1.0


def test_expiration_is_parsed_as_utc():
    order = hd.parse_major_order(order_payload([(1, 2, 2)], "2026-09-25T12:00:00Z"))

    assert order.expires_at == datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    assert order.seconds_left(now) == pytest.approx(86400)


def test_missing_expiration_is_tolerated():
    order = hd.parse_major_order(order_payload([(1, 2, 2)], None))

    assert order.expires_at is None
    assert order.seconds_left() is None


def test_unknown_task_type_is_not_given_fake_precision():
    # A liberation task has no countable target; reporting a percentage from
    # this endpoint would be inventing a number.
    payload = [{
        "id": 1, "title": "MAJOR ORDER", "briefing": "", "progress": [0],
        "tasks": [{"type": 11, "values": [0, 0, 0]}], "expiration": None,
    }]
    task = hd.parse_major_order(payload).tasks[0]

    assert not task.is_measurable
    assert task.fraction == 0.0
    assert "pending" in hd.describe_task(task, 0)


# --------------------------------------------------------------------- planets


def campaign(name, health, max_health, players, regen=0.0, event=None, owner="Terminids"):
    return {
        # The live API always reports "Humans" here; it names who is running
        # the campaign, not who is being fought.
        "faction": "Humans",
        "planet": {
            "name": name, "sector": "Sector", "health": health,
            "maxHealth": max_health, "regenPerSecond": regen,
            "currentOwner": owner, "event": event,
            "statistics": {"playerCount": players},
        },
    }


def test_enemy_faction_comes_from_the_planet_owner_not_the_campaign():
    # Regression: campaign.faction is always "Humans", so using it labelled
    # every enemy planet as friendly.
    planets = hd.parse_planets([campaign("HELD", 500, 1000, 10, owner="Illuminate")])

    assert planets[0].faction == "Illuminate"


def test_liberation_is_inverted_health():
    planets = hd.parse_planets([campaign("ZEA RUGOSIA", 250_000, 1_000_000, 5_000)])

    assert planets[0].name == "Zea Rugosia"
    assert planets[0].liberation == pytest.approx(75.0)


def test_untouched_planet_is_zero_percent():
    planets = hd.parse_planets([campaign("FRESH", 1_000_000, 1_000_000, 10)])

    assert planets[0].liberation == pytest.approx(0.0)


def test_planets_are_sorted_by_player_count():
    planets = hd.parse_planets([
        campaign("QUIET", 500, 1000, 12),
        campaign("BUSY", 500, 1000, 90_000),
        campaign("MIDDLE", 500, 1000, 4_000),
    ])

    assert [planet.name for planet in planets] == ["Busy", "Middle", "Quiet"]


def test_defence_uses_the_event_health():
    event = {"health": 400, "maxHealth": 1000}
    planets = hd.parse_planets([campaign("UNDER SIEGE", 1_000_000, 1_000_000, 5, event=event)])

    assert planets[0].is_defense
    assert planets[0].liberation == pytest.approx(60.0)


def test_regen_is_converted_to_percent_per_hour():
    planets = hd.parse_planets([campaign("SLIPPING", 500, 3600, 1, regen=1.0)])

    # 1 health/sec against 3600 max health is exactly 100% per hour.
    assert planets[0].regen_per_hour == pytest.approx(100.0)


def test_missing_fields_do_not_crash():
    planets = hd.parse_planets([{"planet": {}}])

    assert planets[0].name == "Unknown"
    assert planets[0].players == 0


# ------------------------------------------------------------------ projection

HOUR = 3600.0


def measurable(current, target):
    return hd.Task(kind=hd.TASK_KILL, current=current, target=target, faction="Terminids")


def test_completed_task_reports_done():
    assert hd.project_task(measurable(100, 100), 1.0, HOUR) == "done"


def test_without_history_it_states_the_rate_required():
    verdict = hd.project_task(measurable(0, 3600), None, HOUR)

    assert "needs" in verdict and "/h" in verdict


def test_on_pace_when_the_observed_rate_is_enough():
    # 1 per second for an hour finishes 3600 remaining exactly.
    verdict = hd.project_task(measurable(0, 3600), 1.0, HOUR)

    assert verdict.startswith("on pace")


def test_off_pace_reports_where_it_will_actually_land():
    # Half the needed rate lands at roughly half the target.
    verdict = hd.project_task(measurable(0, 7200), 1.0, HOUR)

    assert verdict.startswith("off pace")
    assert "50%" in verdict


def test_negative_progress_is_called_out():
    assert hd.project_task(measurable(10, 100), -1.0, HOUR) == "going backwards"


def test_expired_order_needs_no_projection():
    assert hd.project_task(measurable(10, 100), 1.0, -5) == "no deadline"


# ------------------------------------------------------------------ formatting


@pytest.mark.parametrize("value,expected", [
    (999, "999"), (1_500, "1.5K"), (2_400_000, "2.4M"), (1_021_651_304, "1.0B"),
])
def test_humanize_count(value, expected):
    assert hd.humanize_count(value) == expected


@pytest.mark.parametrize("seconds,expected", [
    (0, "expired"), (-10, "expired"), (90, "1m"), (7_260, "2h 1m"), (200_000, "2d 7h"),
])
def test_humanize_duration(seconds, expected):
    assert hd.humanize_duration(seconds) == expected


def test_progress_bar_is_fixed_width():
    assert len(hd.progress_bar(0.5, width=10)) == 10
    assert hd.progress_bar(0.0, width=4) == "░" * 4
    assert hd.progress_bar(1.0, width=4) == "█" * 4
    assert hd.progress_bar(5.0, width=4) == "█" * 4  # clamped
