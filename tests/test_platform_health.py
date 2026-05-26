"""
Tests for _platform_status and _compute_health.

Key invariant: the alarm fires exactly once when a platform ENTERS "down"
state — NOT on every heartbeat while it stays there.
"""
import pytest
from unittest.mock import patch


# ── _platform_status ──────────────────────────────────────────────────────────

def test_streak_zero_is_healthy():
    from app.routers.admin import _platform_status
    assert _platform_status(0, 10) == "healthy"

def test_streak_one_is_warning():
    from app.routers.admin import _platform_status
    assert _platform_status(1, 10) == "warning"

def test_streak_threshold_minus_one_is_warning():
    from app.routers.admin import _platform_status
    assert _platform_status(9, 10) == "warning"

def test_streak_at_threshold_is_down():
    from app.routers.admin import _platform_status
    assert _platform_status(10, 10) == "down"

def test_streak_above_threshold_is_down():
    from app.routers.admin import _platform_status
    assert _platform_status(11, 10) == "down"
    assert _platform_status(100, 10) == "down"

def test_custom_threshold():
    from app.routers.admin import _platform_status
    assert _platform_status(4, 5) == "warning"
    assert _platform_status(5, 5) == "down"


# ── alarm transition anti-spam ─────────────────────────────────────────────────
# The alarm condition is: prev_status != "down" AND new_status == "down".
# Prove it fires exactly once on entry and never again while "down".

def test_alarm_fires_only_at_entry_transition():
    from app.routers.admin import _platform_status
    threshold = 10

    # Streak sequence crossing the threshold and staying above it
    streak_sequence = [0, 5, 9, 10, 11, 15, 20]
    statuses = [_platform_status(s, threshold) for s in streak_sequence]

    alarm_fires = [
        (statuses[i], statuses[i + 1])
        for i in range(len(statuses) - 1)
        if statuses[i] != "down" and statuses[i + 1] == "down"
    ]

    assert len(alarm_fires) == 1
    assert alarm_fires[0] == ("warning", "down")

def test_alarm_does_not_refire_while_platform_stays_down():
    from app.routers.admin import _platform_status
    threshold = 10

    # Platform has been "down" for 5 consecutive polls (streaks already above threshold)
    staying_down = [10, 11, 12, 13, 14]
    statuses = [_platform_status(s, threshold) for s in staying_down]

    alarm_fires = sum(
        1 for i in range(1, len(statuses))
        if statuses[i - 1] != "down" and statuses[i] == "down"
    )
    assert alarm_fires == 0, f"Alarm re-fired {alarm_fires} times while platform stayed down"

def test_recovery_fires_only_on_return_to_zero():
    from app.routers.admin import _platform_status
    threshold = 10

    # Down then recovering slowly: 12 → 8 (warning) → 0 (healthy)
    streak_sequence = [12, 8, 0]
    statuses = [_platform_status(s, threshold) for s in streak_sequence]
    # ["down", "warning", "healthy"]

    recovery_fires = [
        (statuses[i], statuses[i + 1])
        for i in range(len(statuses) - 1)
        if statuses[i] == "down" and statuses[i + 1] == "healthy"
    ]
    # No direct down→healthy transition; went down→warning→healthy
    assert len(recovery_fires) == 0

    # A direct drop to 0 from "down" does trigger recovery
    streak_sequence2 = [12, 0]
    statuses2 = [_platform_status(s, threshold) for s in streak_sequence2]
    recovery_fires2 = [
        (statuses2[i], statuses2[i + 1])
        for i in range(len(statuses2) - 1)
        if statuses2[i] == "down" and statuses2[i + 1] == "healthy"
    ]
    assert len(recovery_fires2) == 1


# ── _compute_health ────────────────────────────────────────────────────────────

def test_compute_health_per_platform_verdicts():
    from app.routers.admin import _compute_health

    row = {
        "last_heartbeat": None,
        "last_poll": 42,
        "consecutive_zero_polls": {"gtg": 0, "golfnow": 5, "chronogolf": 10},
        "slots_last_poll": {"gtg": 8, "golfnow": 0, "chronogolf": 0},
        "last_productive_poll": None,
        "sitekey_fallback_active": True,
        "captcha_balance": 3.50,
    }

    with patch.dict("os.environ", {"ALARM_THRESHOLD_POLLS": "10"}):
        result = _compute_health(row)

    assert result["platforms"]["gtg"]["status"] == "healthy"
    assert result["platforms"]["golfnow"]["status"] == "warning"
    assert result["platforms"]["chronogolf"]["status"] == "down"
    assert result["overall_verdict"] == "down"
    assert result["sitekey_fallback_active"] is True
    assert result["captcha_balance"] == pytest.approx(3.50)
    assert result["last_poll_number"] == 42


def test_compute_health_overall_warning_when_no_down():
    from app.routers.admin import _compute_health

    row = {
        "last_heartbeat": None,
        "last_poll": 1,
        "consecutive_zero_polls": {"gtg": 0, "golfnow": 5},
        "slots_last_poll": {},
        "last_productive_poll": None,
        "sitekey_fallback_active": False,
        "captcha_balance": None,
    }

    with patch.dict("os.environ", {"ALARM_THRESHOLD_POLLS": "10"}):
        result = _compute_health(row)

    assert result["overall_verdict"] == "warning"


def test_compute_health_all_healthy():
    from app.routers.admin import _compute_health

    row = {
        "last_heartbeat": None,
        "last_poll": 1,
        "consecutive_zero_polls": {"gtg": 0, "golfnow": 0},
        "slots_last_poll": {"gtg": 5, "golfnow": 3},
        "last_productive_poll": None,
        "sitekey_fallback_active": False,
        "captcha_balance": 10.0,
    }

    with patch.dict("os.environ", {"ALARM_THRESHOLD_POLLS": "10"}):
        result = _compute_health(row)

    assert result["overall_verdict"] == "healthy"
    assert all(p["status"] == "healthy" for p in result["platforms"].values())


def test_compute_health_uses_env_threshold():
    from app.routers.admin import _compute_health

    row = {
        "last_heartbeat": None,
        "last_poll": 0,
        "consecutive_zero_polls": {"gtg": 5},
        "slots_last_poll": {},
        "last_productive_poll": None,
        "sitekey_fallback_active": False,
        "captcha_balance": None,
    }

    with patch.dict("os.environ", {"ALARM_THRESHOLD_POLLS": "5"}):
        result = _compute_health(row)
    assert result["platforms"]["gtg"]["status"] == "down"

    with patch.dict("os.environ", {"ALARM_THRESHOLD_POLLS": "6"}):
        result = _compute_health(row)
    assert result["platforms"]["gtg"]["status"] == "warning"


def test_compute_health_empty_data():
    from app.routers.admin import _compute_health

    with patch.dict("os.environ", {"ALARM_THRESHOLD_POLLS": "10"}):
        result = _compute_health({})

    assert result["platforms"] == {}
    assert result["overall_verdict"] == "healthy"
    assert result["is_healthy"] is False
    assert result["sitekey_fallback_active"] is False
    assert result["captcha_balance"] is None
