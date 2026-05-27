"""
Tests for _compute_platform_alarm_actions — the pure decision function that
drives the per-platform SMS/recovery alarm system.

Required invariants:
  (a) Rising edge (9→10) triggers SMS alarm, CAS-guarded.
  (b) Second heartbeat at/above threshold does NOT re-fire (CAS guard holds).
  (c) Recovery email fires on counter→0 when alarm was active.
  (d) Both platforms can alarm independently in the same heartbeat.
  (e) PER_PLATFORM_ALARM_THRESHOLD env var respected.
  (f) PER_PLATFORM_ALARM_ENABLED=false suppresses SMS (toggle works).
  (g) Recovery is NOT gated on enabled flag — active alarms clear regardless.
  (h) No action when counter rises but stays below threshold.
  (i) No recovery email when counter resets but alarm was never active.
"""

import pytest
from app.routers.admin import _compute_platform_alarm_actions

THRESHOLD = 10


# ── (a) Rising edge fires SMS alarm ──────────────────────────────────────────

def test_rising_edge_9_to_10_fires_sms():
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 9},
        new_streaks={"gtg": 10},
        prev_alarm_active={},
        threshold=THRESHOLD,
        enabled=True,
    )
    assert len(actions) == 1
    action, platform, streak = actions[0]
    assert action == "sms_alarm"
    assert platform == "gtg"
    assert streak == 10
    assert new_alarm["gtg"] is True


# ── (b) CAS guard: no re-fire on second heartbeat at/above threshold ─────────

def test_no_refire_when_already_alarming():
    """Alarm is already active (True). Counter goes 10→11. Must NOT fire again."""
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 10},
        new_streaks={"gtg": 11},
        prev_alarm_active={"gtg": True},
        threshold=THRESHOLD,
        enabled=True,
    )
    assert actions == [], f"expected no actions but got {actions}"
    assert new_alarm["gtg"] is True  # alarm stays active


def test_no_refire_on_many_ticks_while_down():
    """Simulate 20 heartbeats while platform stays down. Zero actions."""
    alarm_active = {"gtg": True}
    for streak in range(10, 30):
        new_alarm, actions = _compute_platform_alarm_actions(
            prev_streaks={"gtg": streak},
            new_streaks={"gtg": streak + 1},
            prev_alarm_active=alarm_active,
            threshold=THRESHOLD,
            enabled=True,
        )
        assert actions == [], f"unexpected action at streak {streak+1}: {actions}"
        alarm_active = new_alarm


# ── (c) Recovery email fires on counter→0 when alarm active ──────────────────

def test_recovery_email_on_counter_reset():
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 15},
        new_streaks={"gtg": 0},
        prev_alarm_active={"gtg": True},
        threshold=THRESHOLD,
        enabled=True,
    )
    assert len(actions) == 1
    action, platform, arg = actions[0]
    assert action == "email_recovery"
    assert platform == "gtg"
    assert arg is None
    assert new_alarm["gtg"] is False


def test_no_recovery_email_if_alarm_was_not_active():
    """Counter resets but alarm was never fired — no spurious recovery email."""
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 5},
        new_streaks={"gtg": 0},
        prev_alarm_active={},
        threshold=THRESHOLD,
        enabled=True,
    )
    assert actions == []


# ── (d) Both platforms alarm independently in same heartbeat ─────────────────

def test_two_platforms_alarm_independently():
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 9, "golfnow": 9},
        new_streaks={"gtg": 10, "golfnow": 10},
        prev_alarm_active={},
        threshold=THRESHOLD,
        enabled=True,
    )
    alarmed_platforms = {a[1] for a in actions}
    assert alarmed_platforms == {"gtg", "golfnow"}
    assert all(a[0] == "sms_alarm" for a in actions)
    assert new_alarm["gtg"] is True
    assert new_alarm["golfnow"] is True


def test_one_platform_alarms_other_recovers():
    """gtg crosses threshold (new alarm); golfnow resets to 0 (recovery)."""
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 9, "golfnow": 12},
        new_streaks={"gtg": 10, "golfnow": 0},
        prev_alarm_active={"golfnow": True},
        threshold=THRESHOLD,
        enabled=True,
    )
    action_map = {a[1]: a[0] for a in actions}
    assert action_map["gtg"] == "sms_alarm"
    assert action_map["golfnow"] == "email_recovery"
    assert new_alarm["gtg"] is True
    assert new_alarm["golfnow"] is False


# ── (e) PER_PLATFORM_ALARM_THRESHOLD env var respected ───────────────────────

def test_threshold_5_fires_at_5():
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 4},
        new_streaks={"gtg": 5},
        prev_alarm_active={},
        threshold=5,
        enabled=True,
    )
    assert len(actions) == 1
    assert actions[0][0] == "sms_alarm"


def test_threshold_10_does_not_fire_at_5():
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 4},
        new_streaks={"gtg": 5},
        prev_alarm_active={},
        threshold=10,
        enabled=True,
    )
    assert actions == []


# ── (f) PER_PLATFORM_ALARM_ENABLED=false suppresses SMS ──────────────────────

def test_disabled_suppresses_sms_alarm():
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 9},
        new_streaks={"gtg": 10},
        prev_alarm_active={},
        threshold=THRESHOLD,
        enabled=False,
    )
    assert actions == []
    assert new_alarm.get("gtg", False) is False  # alarm_active not set


# ── (g) Recovery clears alarm even when enabled=False ────────────────────────

def test_recovery_clears_alarm_even_when_disabled():
    """If alarm was set (from a previous enabled period) and counter resets,
    recovery email still fires and alarm_active clears."""
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 12},
        new_streaks={"gtg": 0},
        prev_alarm_active={"gtg": True},
        threshold=THRESHOLD,
        enabled=False,
    )
    assert len(actions) == 1
    assert actions[0][0] == "email_recovery"
    assert new_alarm["gtg"] is False


# ── (h) No action when below threshold ───────────────────────────────────────

def test_no_action_below_threshold():
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 0},
        new_streaks={"gtg": 5},
        prev_alarm_active={},
        threshold=THRESHOLD,
        enabled=True,
    )
    assert actions == []
    assert new_alarm.get("gtg", False) is False


# ── (i) No recovery for counter drop when alarm inactive ─────────────────────

def test_no_spurious_recovery_on_healthy_reset():
    """Platform goes from 5→0 with no alarm active — no recovery email."""
    new_alarm, actions = _compute_platform_alarm_actions(
        prev_streaks={"gtg": 5},
        new_streaks={"gtg": 0},
        prev_alarm_active={"gtg": False},
        threshold=THRESHOLD,
        enabled=True,
    )
    assert actions == []
