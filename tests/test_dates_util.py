from datetime import datetime, timezone
from app.util.dates import _parse_iso


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
