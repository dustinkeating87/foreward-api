from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

TIMESTAMP_FIELDS = {"created_at", "taken_at", "scanned_at", "fired_at"}

_FAKE_ROWS = [
    {"course_name": "Course A", "tee_time": "08:00", "players": 2},
    {"course_name": "Course B", "tee_time": "09:30", "players": 4},
]


def _mock_supabase(rows):
    chain = MagicMock()
    chain.table.return_value = chain
    chain.select.return_value = chain
    chain.filter.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    return chain


def test_activity_returns_list():
    with patch("app.routers.activity.supabase_admin", _mock_supabase(_FAKE_ROWS)):
        client = TestClient(app)
        r = client.get("/activity")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_activity_default_limit_calls_50():
    mock_db = _mock_supabase(_FAKE_ROWS)
    with patch("app.routers.activity.supabase_admin", mock_db):
        client = TestClient(app)
        client.get("/activity")
    mock_db.limit.assert_called_once_with(50)


def test_activity_custom_limit():
    mock_db = _mock_supabase(_FAKE_ROWS)
    with patch("app.routers.activity.supabase_admin", mock_db):
        client = TestClient(app)
        client.get("/activity?limit=10")
    mock_db.limit.assert_called_once_with(10)


def test_activity_limit_capped_at_100():
    with patch("app.routers.activity.supabase_admin", _mock_supabase(_FAKE_ROWS)):
        client = TestClient(app)
        r = client.get("/activity?limit=999")
    assert r.status_code == 422


def test_activity_no_timestamp_fields():
    # Supabase only returns selected columns; verify the select string excludes timestamps.
    mock_db = _mock_supabase(_FAKE_ROWS)
    with patch("app.routers.activity.supabase_admin", mock_db):
        client = TestClient(app)
        client.get("/activity")
    select_arg = mock_db.select.call_args[0][0]
    selected_cols = {c.strip() for c in select_arg.split(",")}
    assert not TIMESTAMP_FIELDS.intersection(selected_cols), (
        f"Timestamp field in select: {TIMESTAMP_FIELDS.intersection(selected_cols)}"
    )
    # Also verify no timestamp fields appear in the actual response rows.
    with patch("app.routers.activity.supabase_admin", _mock_supabase(_FAKE_ROWS)):
        client = TestClient(app)
        r = client.get("/activity")
    for row in r.json():
        assert not TIMESTAMP_FIELDS.intersection(row.keys()), (
            f"Timestamp field leaked into response: {TIMESTAMP_FIELDS.intersection(row.keys())}"
        )


def test_activity_cache_header():
    with patch("app.routers.activity.supabase_admin", _mock_supabase(_FAKE_ROWS)):
        client = TestClient(app)
        r = client.get("/activity")
    assert "max-age=300" in r.headers.get("cache-control", "")
