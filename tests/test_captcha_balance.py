import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_supabase(row: dict):
    """Minimal Supabase mock that returns `row` for scraper_health select."""
    mock_result = MagicMock()
    mock_result.data = row or None

    select_chain = MagicMock()
    select_chain.eq.return_value = select_chain
    select_chain.maybe_single.return_value = select_chain
    select_chain.execute.return_value = mock_result

    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock()

    table = MagicMock()
    table.select.return_value = select_chain
    table.update.return_value = update_chain

    sb = MagicMock()
    sb.table.return_value = table
    return sb


# ── check_captcha_balance ──────────────────────────────────────────────────────

def test_check_balance_returns_float():
    mock_resp = MagicMock()
    mock_resp.text = "3.45"
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.captcha_balance.httpx.AsyncClient") as cls, \
         patch.dict("os.environ", {"CAPTCHA_API_KEY": "test_key"}):
        cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        cls.return_value.__aexit__ = AsyncMock(return_value=None)
        from app.captcha_balance import check_captcha_balance
        result = run(check_captcha_balance())

    assert result == pytest.approx(3.45)


def test_check_balance_no_key_returns_none():
    with patch.dict("os.environ", {"CAPTCHA_API_KEY": ""}):
        from app.captcha_balance import check_captcha_balance
        result = run(check_captcha_balance())
    assert result is None


def test_check_balance_error_response_returns_none():
    mock_resp = MagicMock()
    mock_resp.text = "ERROR_WRONG_USER_KEY"
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.captcha_balance.httpx.AsyncClient") as cls, \
         patch.dict("os.environ", {"CAPTCHA_API_KEY": "test_key"}):
        cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        cls.return_value.__aexit__ = AsyncMock(return_value=None)
        from app.captcha_balance import check_captcha_balance
        result = run(check_captcha_balance())

    assert result is None


# ── maybe_check_and_alert ──────────────────────────────────────────────────────

_ENV = {
    "CAPTCHA_BALANCE_ALARM_THRESHOLD_USD": "5.0",
    "CAPTCHA_BALANCE_CHECK_INTERVAL_MINUTES": "15",
    "CAPTCHA_API_KEY": "test_key",
}


def test_no_email_when_balance_above_threshold():
    sb = _make_supabase({"captcha_balance_alarmed": False, "last_captcha_balance_check_at": None})

    with patch("app.captcha_balance.check_captcha_balance", new=AsyncMock(return_value=10.0)), \
         patch("app.captcha_balance.send_balance_alarm_email") as alarm, \
         patch("app.captcha_balance.send_balance_recovery_email") as recovery, \
         patch.dict("os.environ", _ENV):
        from app.captcha_balance import maybe_check_and_alert
        run(maybe_check_and_alert(sb))

    alarm.assert_not_called()
    recovery.assert_not_called()


def test_alarm_fires_on_threshold_crossing():
    sb = _make_supabase({"captcha_balance_alarmed": False, "last_captcha_balance_check_at": None})

    with patch("app.captcha_balance.check_captcha_balance", new=AsyncMock(return_value=2.50)), \
         patch("app.captcha_balance.send_balance_alarm_email") as alarm, \
         patch("app.captcha_balance.send_balance_recovery_email") as recovery, \
         patch.dict("os.environ", _ENV):
        from app.captcha_balance import maybe_check_and_alert
        run(maybe_check_and_alert(sb))

    alarm.assert_called_once_with(pytest.approx(2.50), pytest.approx(5.0))
    recovery.assert_not_called()


def test_recovery_fires_when_balance_crosses_back_above():
    sb = _make_supabase({"captcha_balance_alarmed": True, "last_captcha_balance_check_at": None})

    with patch("app.captcha_balance.check_captcha_balance", new=AsyncMock(return_value=8.0)), \
         patch("app.captcha_balance.send_balance_alarm_email") as alarm, \
         patch("app.captcha_balance.send_balance_recovery_email") as recovery, \
         patch.dict("os.environ", _ENV):
        from app.captcha_balance import maybe_check_and_alert
        run(maybe_check_and_alert(sb))

    alarm.assert_not_called()
    recovery.assert_called_once_with(pytest.approx(8.0), pytest.approx(5.0))


def test_no_email_on_api_error():
    sb = _make_supabase({"captcha_balance_alarmed": False, "last_captcha_balance_check_at": None})

    with patch("app.captcha_balance.check_captcha_balance", new=AsyncMock(return_value=None)), \
         patch("app.captcha_balance.send_balance_alarm_email") as alarm, \
         patch("app.captcha_balance.send_balance_recovery_email") as recovery, \
         patch.dict("os.environ", _ENV):
        from app.captcha_balance import maybe_check_and_alert
        run(maybe_check_and_alert(sb))

    alarm.assert_not_called()
    recovery.assert_not_called()
    # DB must not be updated when balance fetch fails
    sb.table("scraper_health").update.assert_not_called()


def test_cooldown_skips_check_within_15min():
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    sb = _make_supabase({"captcha_balance_alarmed": False, "last_captcha_balance_check_at": recent})

    with patch("app.captcha_balance.check_captcha_balance", new=AsyncMock(return_value=3.0)) as mock_check, \
         patch.dict("os.environ", _ENV):
        from app.captcha_balance import maybe_check_and_alert
        run(maybe_check_and_alert(sb))

    mock_check.assert_not_called()


def test_first_check_sets_state_no_email():
    # prev_alarmed = None → first check after migration, no transition to report
    sb = _make_supabase({"captcha_balance_alarmed": None, "last_captcha_balance_check_at": None})

    with patch("app.captcha_balance.check_captcha_balance", new=AsyncMock(return_value=18.72)), \
         patch("app.captcha_balance.send_balance_alarm_email") as alarm, \
         patch("app.captcha_balance.send_balance_recovery_email") as recovery, \
         patch.dict("os.environ", _ENV):
        from app.captcha_balance import maybe_check_and_alert
        run(maybe_check_and_alert(sb))

    alarm.assert_not_called()
    recovery.assert_not_called()
    # State should still be written
    sb.table("scraper_health").update.assert_called_once()
