"""
Tests for POST /scraper/rearm-alert.

Key invariants:
- Only 'fired' or 'expired' alerts may be re-armed; 'active'/'paused' are returned unchanged
- clear_sent_slots=false: status flips, sent_slots untouched
- clear_sent_slots=true: status flips AND sent_slots deleted
- Returns alert_id, resulting status, changed bool, sent_slots_deleted count
"""
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient
from app.main import app

API_KEY = "test-key"


def _db_with_alert(status: str):
    db = MagicMock()

    def table_side(name):
        t = MagicMock()
        t.select.return_value = t
        t.update.return_value = t
        t.delete.return_value = t
        t.eq.return_value = t
        t.maybe_single.return_value = t
        if name == "alert_profiles":
            t.execute.return_value = MagicMock(data={"id": "alert-aaa", "status": status})
        elif name == "sent_slots":
            t.execute.return_value = MagicMock(data=[{"id": "row-1"}, {"id": "row-2"}])
        return t

    db.table.side_effect = table_side
    return db


def _post(mock_db, payload):
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as s:
        s.export_api_key = API_KEY
        return TestClient(app).post(
            "/scraper/rearm-alert",
            json=payload,
            headers={"X-Api-Key": API_KEY},
        )


def test_fired_alert_rearms_to_active():
    r = _post(_db_with_alert("fired"), {"alert_id": "alert-aaa", "clear_sent_slots": False})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"
    assert data["changed"] is True
    assert data["sent_slots_deleted"] == 0


def test_expired_alert_rearms_to_active():
    r = _post(_db_with_alert("expired"), {"alert_id": "alert-aaa"})
    assert r.status_code == 200
    assert r.json()["changed"] is True


def test_active_alert_not_changed():
    mock_db = _db_with_alert("active")
    r = _post(mock_db, {"alert_id": "alert-aaa"})
    assert r.status_code == 200
    data = r.json()
    assert data["changed"] is False
    assert data["status"] == "active"
    update_calls = [c for c in mock_db.method_calls if "update" in str(c)]
    assert not update_calls, "alert_profiles.update must not be called for already-active alert"


def test_paused_alert_not_changed():
    r = _post(_db_with_alert("paused"), {"alert_id": "alert-aaa"})
    assert r.status_code == 200
    assert r.json()["changed"] is False
    assert r.json()["status"] == "paused"


def test_clear_sent_slots_true_deletes_rows():
    r = _post(_db_with_alert("fired"), {"alert_id": "alert-aaa", "clear_sent_slots": True})
    assert r.status_code == 200
    data = r.json()
    assert data["sent_slots_deleted"] == 2  # mock returns 2 rows
    assert data["changed"] is True


def test_clear_sent_slots_false_does_not_delete():
    mock_db = _db_with_alert("fired")
    r = _post(mock_db, {"alert_id": "alert-aaa", "clear_sent_slots": False})
    assert r.status_code == 200
    assert r.json()["sent_slots_deleted"] == 0
    delete_calls = [c for c in mock_db.method_calls if "delete" in str(c)]
    assert not delete_calls, "sent_slots.delete must not be called when clear_sent_slots=false"


def test_missing_alert_returns_404():
    db = MagicMock()
    t = MagicMock()
    t.select.return_value = t
    t.eq.return_value = t
    t.maybe_single.return_value = t
    t.execute.return_value = MagicMock(data=None)
    db.table.return_value = t
    r = _post(db, {"alert_id": "nonexistent"})
    assert r.status_code == 404
