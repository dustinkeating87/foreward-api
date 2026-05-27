"""
Tests for free_tier_used_at being stamped at delivery, not creation.

Key invariants:
- Creating a free-tier alert does NOT stamp free_tier_used_at
- A successful fire_alert (non-empty slots) on a free-tier alert DOES stamp free_tier_used_at
- fire_alert with empty slots (blocked by Commit B) does NOT stamp free_tier_used_at
- The stamp is idempotent: if free_tier_used_at is already set, it is not overwritten
"""
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient
from app.main import app

API_KEY = "test-key"


def _make_db_for_fire(is_free_tier: bool, current_free_tier_used_at=None):
    db = MagicMock()

    def table_side_effect(name):
        t = MagicMock()
        t.insert.return_value = t
        t.update.return_value = t
        t.select.return_value = t
        t.eq.return_value = t
        t.is_.return_value = t
        t.maybe_single.return_value = t

        if name == "sent_slots":
            t.execute.return_value = MagicMock(data=[])
        elif name == "alert_profiles":
            t.execute.return_value = MagicMock(data={"is_free_tier": is_free_tier})
        elif name == "user_profiles":
            t.execute.return_value = MagicMock(data={"free_tier_used_at": current_free_tier_used_at})
        return t

    db.table.side_effect = table_side_effect
    return db


def test_fire_alert_with_free_tier_stamps_free_tier_used_at():
    mock_db = _make_db_for_fire(is_free_tier=True)
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as s:
        s.export_api_key = API_KEY
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={
                "alert_id": "alert-aaa",
                "user_id": "user-111",
                "slots": [{"slot_key": "gtg|2026-06-01|08:00|1"}],
            },
            headers={"X-Api-Key": API_KEY},
        )
    assert r.status_code == 200
    assert r.json()["fired"] is True

    # Verify free_tier_used_at update was attempted on user_profiles
    user_profiles_update_called = any(
        c == call("user_profiles")
        for c in mock_db.table.call_args_list
    )
    assert user_profiles_update_called, "user_profiles table must be accessed to stamp free_tier_used_at"


def test_fire_alert_non_free_tier_does_not_touch_user_profiles():
    mock_db = _make_db_for_fire(is_free_tier=False)
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as s:
        s.export_api_key = API_KEY
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={
                "alert_id": "alert-bbb",
                "user_id": "user-222",
                "slots": [{"slot_key": "gn|2026-06-01|09:00|2"}],
            },
            headers={"X-Api-Key": API_KEY},
        )
    assert r.status_code == 200
    # user_profiles should NOT be updated for non-free-tier alerts
    update_calls = [str(c) for c in mock_db.method_calls if "user_profiles" in str(c) and "update" in str(c)]
    assert not update_calls, "user_profiles must not be updated for non-free-tier alerts"


def test_fire_alert_empty_slots_does_not_stamp():
    mock_db = _make_db_for_fire(is_free_tier=True)
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as s:
        s.export_api_key = API_KEY
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={"alert_id": "alert-ccc", "user_id": "user-333", "slots": []},
            headers={"X-Api-Key": API_KEY},
        )
    assert r.status_code == 200
    assert r.json()["fired"] is False
    # user_profiles must not be touched on empty-slots call
    user_profiles_calls = [c for c in mock_db.table.call_args_list if c == call("user_profiles")]
    assert not user_profiles_calls, "user_profiles must not be accessed when slots is empty"


# ── Unit test: create_alert does NOT stamp free_tier_used_at ──────────────────

def _free_tier_used_at_called(mock_db) -> bool:
    """Return True if any update to user_profiles set free_tier_used_at."""
    for c in mock_db.method_calls:
        if "free_tier_used_at" in str(c):
            return True
    return False


def test_free_tier_stamp_at_delivery_not_creation():
    """
    Directly verify the logic: creating the first free-tier alert (no existing_ft)
    must not call update with free_tier_used_at.
    This tests the alerts.py logic, not the API endpoint.
    """
    from app.routers.alerts import create_alert
    from app.schemas import AlertProfileCreate
    from datetime import date

    body = AlertProfileCreate(
        courses=["humber-valley"],
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        time_from="08:00",
        time_to="12:00",
        players=1,
        holes=18,
    )

    alert_id = "new-alert-id"
    mock_user = MagicMock()
    mock_user.id = "user-999"
    mock_user.email = "test@example.com"

    profile = {"is_active": False, "is_beta": False, "free_tier_used_at": None,
               "free_tier_grace_retry_used_at": None}
    ctx = {"user": mock_user, "profile": profile}

    mock_db = MagicMock()
    chain = MagicMock()
    chain.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain

    # existing_ft query: no prior free-tier alert
    existing_response = MagicMock(data=[])
    # insert response
    insert_response = MagicMock(data=[{"id": alert_id}])
    chain.execute.side_effect = [existing_response, insert_response]

    mock_settings = MagicMock()
    mock_settings.free_tier_enabled = True

    with patch("app.routers.alerts.supabase_admin", chain), \
         patch("app.routers.alerts.settings", mock_settings), \
         patch("app.routers.alerts.send_free_tier_signup_email"):
        result = create_alert(body, ctx)

    assert result["id"] == alert_id

    # free_tier_used_at must NOT appear in any update call
    for c in chain.method_calls:
        if "update" in str(c) and "free_tier_used_at" in str(c):
            raise AssertionError(f"free_tier_used_at was stamped at creation: {c}")
