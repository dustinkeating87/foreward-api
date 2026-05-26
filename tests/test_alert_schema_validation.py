"""
Server-side validation tests for AlertProfileCreate.
Covers all three create-alert code paths (paid / free-tier first / grace retry)
because they all use the same AlertProfileCreate model.
"""
import pytest
from datetime import date, timedelta
from pydantic import ValidationError

from app.schemas import AlertProfileCreate


TOMORROW = date.today() + timedelta(days=1)
NEXT_WEEK = date.today() + timedelta(days=7)
YESTERDAY = date.today() - timedelta(days=1)


def _valid_payload(**overrides):
    base = dict(
        courses=["kings-riding"],
        date_from=TOMORROW,
        date_to=NEXT_WEEK,
        time_from="07:00",
        time_to="13:00",
        players=2,
        holes=18,
    )
    base.update(overrides)
    return base


def test_valid_alert_passes():
    alert = AlertProfileCreate(**_valid_payload())
    assert alert.date_from == TOMORROW
    assert alert.date_to == NEXT_WEEK


def test_date_to_before_date_from_rejected():
    with pytest.raises(ValidationError, match="End date must be on or after start date"):
        AlertProfileCreate(**_valid_payload(date_from=NEXT_WEEK, date_to=TOMORROW))


def test_date_to_in_past_rejected():
    with pytest.raises(ValidationError, match="End date is in the past"):
        AlertProfileCreate(**_valid_payload(date_from=YESTERDAY - timedelta(days=1), date_to=YESTERDAY))


def test_date_to_today_is_valid():
    # An alert ending today can still fire today — must NOT be rejected.
    alert = AlertProfileCreate(**_valid_payload(date_from=date.today(), date_to=date.today()))
    assert alert.date_to == date.today()


def test_inverted_time_window_rejected():
    with pytest.raises(ValidationError, match="Start time must be before end time"):
        AlertProfileCreate(**_valid_payload(time_from="14:00", time_to="08:00"))


def test_equal_time_window_rejected():
    with pytest.raises(ValidationError, match="Start time must be before end time"):
        AlertProfileCreate(**_valid_payload(time_from="09:00", time_to="09:00"))


def test_malformed_time_from_rejected():
    with pytest.raises(ValidationError, match="time_from must be in HH:MM format"):
        AlertProfileCreate(**_valid_payload(time_from="9:00"))


def test_malformed_time_to_rejected():
    with pytest.raises(ValidationError, match="time_to must be in HH:MM format"):
        AlertProfileCreate(**_valid_payload(time_to="2pm"))
