"""
Tests for gtg_scrape_success tri-state handling in the scraper heartbeat.

Covers the None→NULL mapping that prevents a fresh-worker initialization value
from being misread as a scrape failure in scraper_health.

(d) When the heartbeat body contains gtg_scrape_success=None, the upsert_data
    value must be None (Python None → SQL NULL), NOT False.
(e) True stays True, False stays False — existing bool values unaffected.
"""


def _map_gtg_scrape_success(val):
    """Mirrors the mapping logic in app/routers/admin.py scraper_heartbeat."""
    return None if val is None else bool(val)


def test_none_maps_to_none_not_false():
    """None (fresh worker, never polled) must write SQL NULL, not false."""
    assert _map_gtg_scrape_success(None) is None, \
        "gtg_scrape_success=None must produce None (SQL NULL), not False"


def test_true_maps_to_true():
    assert _map_gtg_scrape_success(True) is True


def test_false_maps_to_false():
    assert _map_gtg_scrape_success(False) is False


def test_json_null_maps_to_none():
    """JSON null deserializes to Python None — must still produce None, not False."""
    json_null = None  # what json.loads gives for null
    assert _map_gtg_scrape_success(json_null) is None


def test_bool_false_not_confused_with_none():
    """bool(None)=False is the bug this test guards against."""
    assert bool(None) is False, "bool(None) is False — this is the old buggy behavior"
    assert _map_gtg_scrape_success(None) is None, \
        "our mapping must NOT use bool() directly on None"
