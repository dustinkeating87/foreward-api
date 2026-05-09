"""
Block 7 — distinct error strings for /auth/signup-free-tier.

Tests the three 401 failure paths added in Block 7. Status-code coverage for
these same paths lives in test_signup_free_tier.py (AC3, AC4,
test_regression_no_token_row_returns_401_not_500) and is intentionally NOT
duplicated here. This file only asserts the new specific detail strings.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from app.util.phone import hash_phone
from app.schemas import SignupFreeTierRequest

PHONE_A = "+14155551234"
PHONE_B = "+15555550002"
TOKEN = "some-token-abc"
EMAIL = "user@example.com"
PASSWORD = "password123"


def _request(phone=PHONE_A):
    return SignupFreeTierRequest(
        email=EMAIL,
        password=PASSWORD,
        phone_e164=phone,
        verification_token=TOKEN,
    )


def _mock_admin_no_token():
    """Simulates 0 rows returned for the token lookup."""
    mock = MagicMock()
    t = MagicMock()
    t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    mock.table.return_value = t
    return mock


def _mock_admin_expired_token():
    """Simulates a token row whose token_expires_at is in the past."""
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    row = {"id": "pvc-1", "token_expires_at": expired, "phone_hash": hash_phone(PHONE_A)}
    mock = MagicMock()
    t = MagicMock()
    t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [row]
    mock.table.return_value = t
    return mock


def _mock_admin_phone_mismatch():
    """Simulates a valid token row whose phone_hash belongs to a different phone."""
    future = (datetime.now(timezone.utc) + timedelta(minutes=25)).isoformat()
    row = {"id": "pvc-1", "token_expires_at": future, "phone_hash": hash_phone("+15555550001")}
    mock = MagicMock()
    t = MagicMock()
    t.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [row]
    mock.table.return_value = t
    return mock


def test_signup_free_tier_token_not_found():
    from app.routers.auth import signup_free_tier
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", _mock_admin_no_token()):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 401
    assert exc.value.detail == "Verification token not recognized."


def test_signup_free_tier_token_expired():
    from app.routers.auth import signup_free_tier
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", _mock_admin_expired_token()):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 401
    assert exc.value.detail == "Verification token has expired. Please request a new code."


def test_signup_free_tier_phone_mismatch():
    from app.routers.auth import signup_free_tier
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", _mock_admin_phone_mismatch()):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request(phone=PHONE_B))
    assert exc.value.status_code == 401
    assert exc.value.detail == "This verification code was sent to a different phone number. Please use the same number you entered when requesting the code."
