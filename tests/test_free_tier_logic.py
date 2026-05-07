from datetime import datetime, timezone, timedelta
from typing import Optional
import pytest

from app.util.dates import _parse_iso


# ── _parse_iso ─────────────────────────────────────────────────────────────────

def test_parse_iso_standard_6_digit():
    result = _parse_iso("2026-05-07T00:55:46.123456+00:00")
    assert result == datetime(2026, 5, 7, 0, 55, 46, 123456, tzinfo=timezone.utc)


def test_parse_iso_5_digit_pads_to_6():
    # Python 3.9 raises ValueError on this without the helper
    result = _parse_iso("2026-05-07T00:55:46.20461+00:00")
    assert result.microsecond == 204610


def test_parse_iso_3_digit_pads_to_6():
    result = _parse_iso("2026-05-07T00:55:46.123+00:00")
    assert result.microsecond == 123000


def test_parse_iso_no_fractional():
    result = _parse_iso("2026-05-07T00:55:46+00:00")
    assert result.second == 46
    assert result.microsecond == 0


def test_parse_iso_z_suffix():
    result = _parse_iso("2026-05-07T00:55:46.123456Z")
    assert result.utcoffset().total_seconds() == 0


def test_parse_iso_negative_offset():
    result = _parse_iso("2026-05-07T00:55:46.123456-05:00")
    assert result.utcoffset().total_seconds() == -5 * 3600


# ── Free-tier user classification (mirrors logic in create_alert) ──────────────
# Defined here as a pure helper so the test doesn't import the FastAPI app.

def _classify_free_tier_user(profile: dict, free_tier_enabled: bool) -> str:
    is_paid = bool(profile.get("is_active") or profile.get("is_beta"))
    if is_paid:
        return "paid"
    if not free_tier_enabled:
        return "flag_off"
    if profile.get("final_expired_at"):
        return "blocked"
    if profile.get("free_tier_used_at"):
        return "already_used"
    return "eligible"


def test_classify_is_active_paid():
    assert _classify_free_tier_user({"is_active": True}, True) == "paid"


def test_classify_is_beta_paid():
    assert _classify_free_tier_user({"is_beta": True}, True) == "paid"


def test_classify_paid_flag_off_still_paid():
    # Paid users are never affected by the flag
    assert _classify_free_tier_user({"is_active": True}, False) == "paid"


def test_classify_flag_off_unpaid():
    assert _classify_free_tier_user({}, False) == "flag_off"


def test_classify_permanently_blocked():
    profile = {"final_expired_at": "2026-04-01T00:00:00+00:00"}
    assert _classify_free_tier_user(profile, True) == "blocked"


def test_classify_already_used():
    profile = {"free_tier_used_at": "2026-04-01T00:00:00+00:00"}
    assert _classify_free_tier_user(profile, True) == "already_used"


def test_classify_eligible_new_user():
    assert _classify_free_tier_user({}, True) == "eligible"


# ── Expiry transition classification (mirrors logic in check_free_tier_expiry) ──

def _classify_expiry_action(alert: dict, now: datetime) -> Optional[str]:
    if not alert.get("is_free_tier"):
        return None
    if alert.get("status") != "active":
        return None
    if alert.get("expiry_state") is not None:
        return None
    expires_at_str = alert.get("polling_expires_at")
    if not expires_at_str:
        return None
    if now <= _parse_iso(expires_at_str):
        return None
    renewals_used = alert.get("renewals_used") or 0
    return "pending_renewal" if renewals_used < 2 else "final_expired"


def test_expiry_not_free_tier():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": False, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_not_yet_expired():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now + timedelta(days=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_already_has_state():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": "expired_pending_renewal",
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_not_active():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "expired", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) is None


def test_expiry_first_window_pending_renewal():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 0}
    assert _classify_expiry_action(alert, now) == "pending_renewal"


def test_expiry_after_first_renewal_still_pending():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 1}
    assert _classify_expiry_action(alert, now) == "pending_renewal"


def test_expiry_after_two_renewals_final():
    now = datetime.now(timezone.utc)
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": (now - timedelta(hours=1)).isoformat(), "renewals_used": 2}
    assert _classify_expiry_action(alert, now) == "final_expired"


def test_expiry_5_digit_microsecond_timestamp():
    # Regression: ensure expiry works even when Supabase returns 5-digit microseconds
    now = datetime.now(timezone.utc)
    past = "2026-04-01T00:55:46.20461+00:00"  # 5-digit microseconds
    alert = {"is_free_tier": True, "status": "active", "expiry_state": None,
             "polling_expires_at": past, "renewals_used": 0}
    assert _classify_expiry_action(alert, now) == "pending_renewal"
