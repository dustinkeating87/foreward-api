from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from app.util.phone import hash_phone
from app.schemas import SignupFreeTierRequest

PHONE = "+14155551234"
PHONE_HASH = hash_phone(PHONE)
TOKEN = "valid-token-xyz"
EMAIL = "newuser@example.com"
PASSWORD = "password123"
USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _request(**overrides):
    defaults = dict(email=EMAIL, password=PASSWORD, phone_e164=PHONE, verification_token=TOKEN)
    defaults.update(overrides)
    return SignupFreeTierRequest(**defaults)


def _future_iso():
    return (datetime.now(timezone.utc) + timedelta(minutes=25)).isoformat()


def _valid_token_row():
    return {"id": "pvc-id-1", "used": False, "token_expires_at": _future_iso(), "phone_hash": PHONE_HASH}


def _mock_admin(token_row=None, phone_unique=True, create_user_exc=None, update_exc=None):
    """Build a supabase_admin mock for the signup-free-tier flow."""
    mock = MagicMock()

    # phone_verification_codes lookup
    pvc_select = MagicMock()
    pvc_select.eq.return_value.maybe_single.return_value.execute.return_value.data = token_row
    mock.table.return_value.select.return_value = pvc_select

    # Override table() to return appropriate mock per table name
    def table_factory(name):
        t = MagicMock()
        if name == "phone_verification_codes":
            t.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = token_row
            t.update.return_value.eq.return_value.execute.return_value.data = [{"id": "pvc-id-1"}]
        elif name == "user_profiles":
            t.select.return_value.eq.return_value.not_.is_.return_value.maybe_single.return_value.execute.return_value.data = (
                None if phone_unique else {"id": "existing-user"}
            )
            if update_exc:
                t.update.return_value.eq.return_value.execute.side_effect = update_exc
            else:
                t.update.return_value.eq.return_value.execute.return_value.data = [{"id": USER_ID}]
        return t

    mock.table.side_effect = table_factory

    if create_user_exc:
        mock.auth.admin.create_user.side_effect = create_user_exc
    else:
        mock.auth.admin.create_user.return_value.user.id = USER_ID
        mock.auth.admin.create_user.return_value.user.email = EMAIL

    mock.auth.admin.delete_user.return_value = None
    return mock


def _mock_supabase():
    mock = MagicMock()
    mock.auth.sign_in_with_password.return_value.session.access_token = "access-tok"
    mock.auth.sign_in_with_password.return_value.session.refresh_token = "refresh-tok"
    return mock


# ── AC0: Kill switch ──────────────────────────────────────────────────────────

def test_ac0_kill_switch_returns_503():
    from app.routers.auth import signup_free_tier
    with patch("app.routers.auth.settings") as mock_settings:
        mock_settings.free_tier_enabled = False
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 503


# ── AC1: Happy path ───────────────────────────────────────────────────────────

def test_ac1_happy_path_returns_201_shape():
    from app.routers.auth import signup_free_tier
    mock_admin = _mock_admin(token_row=_valid_token_row(), phone_unique=True)
    mock_supa = _mock_supabase()
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", mock_admin), \
         patch("app.routers.auth.supabase", mock_supa):
        ms.free_tier_enabled = True
        result = signup_free_tier(_request())
    assert result["token_type"] == "bearer"
    assert result["user"]["tier"] == "free"
    assert "access_token" in result
    assert "refresh_token" in result


# ── AC2: Used token → 401 ─────────────────────────────────────────────────────

def test_ac2_used_token_returns_401():
    from app.routers.auth import signup_free_tier
    used_row = {**_valid_token_row(), "used": True}
    mock_admin = _mock_admin(token_row=used_row)
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", mock_admin):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 401


# ── AC3: Expired token → 401 ──────────────────────────────────────────────────

def test_ac3_expired_token_returns_401():
    from app.routers.auth import signup_free_tier
    expired_row = {**_valid_token_row(), "token_expires_at": "2020-01-01T00:00:00+00:00"}
    mock_admin = _mock_admin(token_row=expired_row)
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", mock_admin):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 401


# ── AC4: Phone mismatch → 401 ─────────────────────────────────────────────────

def test_ac4_phone_mismatch_returns_401():
    from app.routers.auth import signup_free_tier
    wrong_hash_row = {**_valid_token_row(), "phone_hash": hash_phone("+19995550000")}
    mock_admin = _mock_admin(token_row=wrong_hash_row)
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", mock_admin):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 401


# ── AC5: Phone already claimed → 409 ─────────────────────────────────────────

def test_ac5_phone_already_claimed_returns_409():
    from app.routers.auth import signup_free_tier
    mock_admin = _mock_admin(token_row=_valid_token_row(), phone_unique=False)
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", mock_admin):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 409
    assert "Phone" in exc.value.detail or "phone" in exc.value.detail


# ── AC6: Email already exists → 409 ──────────────────────────────────────────

def test_ac6_email_already_exists_returns_409():
    from app.routers.auth import signup_free_tier
    mock_admin = _mock_admin(
        token_row=_valid_token_row(),
        phone_unique=True,
        create_user_exc=Exception("User already registered"),
    )
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", mock_admin):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 409


# ── AC7: Compensating delete on mid-flow failure → 500 ───────────────────────

def test_ac7_compensating_delete_on_profile_update_failure():
    from app.routers.auth import signup_free_tier
    mock_admin = _mock_admin(
        token_row=_valid_token_row(),
        phone_unique=True,
        update_exc=Exception("DB write failed"),
    )
    mock_supa = _mock_supabase()
    with patch("app.routers.auth.settings") as ms, \
         patch("app.routers.auth.supabase_admin", mock_admin), \
         patch("app.routers.auth.supabase", mock_supa):
        ms.free_tier_enabled = True
        with pytest.raises(HTTPException) as exc:
            signup_free_tier(_request())
    assert exc.value.status_code == 500
    # Verify compensating delete was called
    mock_admin.auth.admin.delete_user.assert_called_once_with(USER_ID)


# ── AC8: Paid /auth/signup regression ────────────────────────────────────────

def test_ac8_paid_signup_unaffected():
    from app.routers.auth import signup
    from app.schemas import SignupRequest
    mock_admin = MagicMock()
    mock_admin.auth.admin.create_user.return_value.user.id = USER_ID
    mock_admin.auth.admin.create_user.return_value.user.email = EMAIL
    mock_supa = _mock_supabase()
    with patch("app.routers.auth.supabase_admin", mock_admin), \
         patch("app.routers.auth.supabase", mock_supa):
        result = signup(SignupRequest(email=EMAIL, password=PASSWORD))
    assert "access_token" in result
    assert result["user"]["email"] == EMAIL
    # Paid signup has no "tier" field
    assert "tier" not in result["user"]
