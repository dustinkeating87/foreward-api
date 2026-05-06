import hashlib
from app.util.phone import hash_phone, is_valid_e164


def test_hash_phone_is_sha256_hex():
    phone = "+14155551234"
    expected = hashlib.sha256(phone.encode()).hexdigest()
    assert hash_phone(phone) == expected


def test_hash_phone_is_deterministic():
    phone = "+14155551234"
    assert hash_phone(phone) == hash_phone(phone)


def test_hash_phone_different_phones_differ():
    assert hash_phone("+14155551234") != hash_phone("+14155551235")


def test_is_valid_e164_accepts_valid():
    assert is_valid_e164("+14155551234")
    assert is_valid_e164("+16135551234")
    assert is_valid_e164("+447911123456")


def test_is_valid_e164_rejects_no_plus():
    assert not is_valid_e164("14155551234")


def test_is_valid_e164_rejects_too_short():
    assert not is_valid_e164("+123")


def test_is_valid_e164_rejects_letters():
    assert not is_valid_e164("+1415abc1234")


def test_is_valid_e164_rejects_plus_only():
    assert not is_valid_e164("+")
