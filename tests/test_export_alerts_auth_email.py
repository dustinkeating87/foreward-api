"""
Tests for /export-alerts auth-email fallback.

Key invariants:
- When notify_email and notify_phone are both null on user_profiles and alert_profiles,
  the resolved email falls through to auth.users.email (auth_email).
- When notify_email is set, it takes priority over auth_email.
- auth_email is exposed as a separate field in every exported alert dict.
"""
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


API_KEY = "test-key"

_BASE_ALERT = {
    "id": "alert-aaa",
    "user_id": "user-111",
    "status": "active",
    "notify_email": None,
    "notify_phone": None,
    "courses": ["humber-valley"],
    "date_from": "2026-06-01",
    "date_to": "2026-06-30",
    "time_from": "08:00",
    "time_to": "12:00",
    "players": 1,
    "holes": 18,
    "is_free_tier": True,
}


def _auth_user(email):
    user = MagicMock()
    user.email = email
    resp = MagicMock()
    resp.user = user
    return resp


def _make_db(alert_overrides=None, profile_overrides=None):
    alert = {**_BASE_ALERT, **(alert_overrides or {})}
    profile = {"id": "user-111", "notify_email": None, "notify_phone": None, "is_active": False,
               **(profile_overrides or {})}

    db = MagicMock()

    def table_side_effect(name):
        t = MagicMock()
        if name == "alert_profiles":
            t.select.return_value = t
            t.eq.return_value = t
            t.execute.return_value = MagicMock(data=[alert])
        elif name == "user_profiles":
            t.select.return_value = t
            t.in_.return_value = t
            t.execute.return_value = MagicMock(data=[profile])
        return t

    db.table.side_effect = table_side_effect
    return db


def test_null_notify_falls_through_to_auth_email():
    mock_db = _make_db()
    mock_db.auth.admin.get_user_by_id.return_value = _auth_user("rsantoo@rogers.com")

    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as s:
        s.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.get("/export-alerts", headers={"X-Api-Key": API_KEY})

    assert r.status_code == 200
    alerts = r.json()
    assert len(alerts) == 1
    assert alerts[0]["email"] == "rsantoo@rogers.com"
    assert alerts[0]["auth_email"] == "rsantoo@rogers.com"


def test_notify_email_takes_priority_over_auth_email():
    mock_db = _make_db(profile_overrides={"notify_email": "pref@example.com"})
    mock_db.auth.admin.get_user_by_id.return_value = _auth_user("auth@example.com")

    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as s:
        s.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.get("/export-alerts", headers={"X-Api-Key": API_KEY})

    assert r.status_code == 200
    result = r.json()[0]
    assert result["email"] == "pref@example.com"
    assert result["auth_email"] == "auth@example.com"


def test_auth_email_field_always_present():
    """auth_email key must exist on every alert dict regardless of whether it resolves."""
    mock_db = _make_db()
    mock_db.auth.admin.get_user_by_id.side_effect = Exception("auth lookup failed")

    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as s:
        s.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.get("/export-alerts", headers={"X-Api-Key": API_KEY})

    assert r.status_code == 200
    result = r.json()[0]
    assert "auth_email" in result
    assert result["auth_email"] == ""
    assert result["email"] == ""
