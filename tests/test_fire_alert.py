"""
Tests for /scraper/fire-alert endpoint.

Key invariants:
- Empty slots payload must NOT flip alert status to 'fired'
- Non-empty slots payload inserts sent_slots rows and flips status
"""
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient


API_KEY = "test-key"


def _make_db():
    chain = MagicMock()
    chain.table.return_value = chain
    chain.update.return_value = chain
    chain.insert.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    return chain


def _client(mock_db):
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as mock_settings:
        mock_settings.export_api_key = API_KEY
        from app.main import app
        return TestClient(app)


def test_empty_slots_does_not_flip_status():
    mock_db = _make_db()
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as mock_settings:
        mock_settings.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={"alert_id": "aaa", "user_id": None, "slots": []},
            headers={"X-Api-Key": API_KEY},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["fired"] is False
    assert data["reason"] == "no_slots"
    # status update must never have been called
    update_calls = [str(c) for c in mock_db.method_calls if "update" in str(c)]
    assert not any("fired" in c for c in update_calls), \
        "status must not be set to 'fired' when slots is empty"


def test_non_empty_slots_flips_status():
    mock_db = _make_db()
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as mock_settings:
        mock_settings.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={
                "alert_id": "bbb",
                "user_id": "uid-1",
                "slots": [{"slot_key": "gtg|2026-06-01|08:00|2", "course_name": "Humber Valley"}],
            },
            headers={"X-Api-Key": API_KEY},
        )
    assert r.status_code == 200
    assert r.json()["fired"] is True
    # status='fired' update must be in the update calls (may also include free_tier_used_at stamp)
    update_args = [c.args[0] for c in mock_db.update.call_args_list]
    assert {"status": "fired"} in update_args


def test_empty_slots_returns_ok_false_fired():
    """Response shape: ok=True, fired=False on empty slots."""
    mock_db = _make_db()
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as mock_settings:
        mock_settings.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={"alert_id": "ccc", "slots": []},
            headers={"X-Api-Key": API_KEY},
        )
    assert r.json() == {"ok": True, "fired": False, "reason": "no_slots"}


def test_success_response_includes_slot_counts():
    """Successful insert returns slots_written=N, slots_failed=0."""
    mock_db = _make_db()
    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as mock_settings:
        mock_settings.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={
                "alert_id": "ddd",
                "slots": [
                    {"slot_key": "HV|12:10:00|18"},
                    {"slot_key": "HV|13:20:00|18"},
                ],
            },
            headers={"X-Api-Key": API_KEY},
        )
    data = r.json()
    assert r.status_code == 200
    assert data["fired"] is True
    assert data["slots_written"] == 2
    assert data["slots_failed"] == 0


def test_bulk_insert_failure_falls_back_per_row_and_reports_counts():
    """When bulk insert raises, per-row fallback runs; response reflects per-row results."""
    mock_db = _make_db()
    call_count = {"n": 0}

    def insert_side_effect(data):
        call_count["n"] += 1
        if isinstance(data, list):
            # bulk fails
            raise Exception("timestamptz cast error")
        # per-row: first succeeds, second fails
        chain = MagicMock()
        if call_count["n"] == 2:
            chain.execute.side_effect = Exception("per-row failure")
        else:
            chain.execute.return_value = MagicMock(data=[{}])
        return chain

    mock_db.table.return_value.insert.side_effect = insert_side_effect

    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as mock_settings:
        mock_settings.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={
                "alert_id": "eee",
                "slots": [
                    {"slot_key": "HV|12:10:00|18"},
                    {"slot_key": "HV|13:20:00|18"},
                ],
            },
            headers={"X-Api-Key": API_KEY},
        )
    data = r.json()
    assert r.status_code == 200
    assert data["fired"] is True
    assert data["slots_written"] + data["slots_failed"] == 2


def test_total_insert_failure_still_fires_with_zero_written():
    """All rows fail → slots_written=0, slots_failed=N, alert still fired (delivery already sent)."""
    mock_db = _make_db()

    def always_fail(data):
        chain = MagicMock()
        chain.execute.side_effect = Exception("DB down")
        return chain

    mock_db.table.return_value.insert.side_effect = always_fail

    with patch("app.main.supabase_admin", mock_db), \
         patch("app.main.settings") as mock_settings:
        mock_settings.export_api_key = API_KEY
        from app.main import app
        client = TestClient(app)
        r = client.post(
            "/scraper/fire-alert",
            json={
                "alert_id": "fff",
                "slots": [{"slot_key": "HV|12:10:00|18"}],
            },
            headers={"X-Api-Key": API_KEY},
        )
    data = r.json()
    assert r.status_code == 200
    assert data["fired"] is True
    assert data["slots_written"] == 0
    assert data["slots_failed"] == 1
