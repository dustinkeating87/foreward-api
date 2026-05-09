def _is_user_free_tier(profile: dict) -> bool:
    return bool(profile.get("free_tier_used_at") and not profile.get("is_active"))


def test_is_user_free_tier_true_for_free_tier_user():
    profile = {"free_tier_used_at": "2026-05-01T00:00:00+00:00", "is_active": False}
    assert _is_user_free_tier(profile) is True


def test_is_user_free_tier_false_for_paid_user():
    assert _is_user_free_tier({"is_active": True, "free_tier_used_at": "2026-05-01T00:00:00+00:00"}) is False


def test_is_user_free_tier_false_for_new_user():
    assert _is_user_free_tier({}) is False


def test_is_user_free_tier_false_for_lapsed_paid_no_free_tier_history():
    # Lapsed paid, never used free tier — free_tier_used_at is NULL
    assert _is_user_free_tier({"is_active": False}) is False


def test_is_user_free_tier_true_lapsed_paid_with_free_tier_history():
    # Was paid, subscription lapsed, previously had free-tier alert
    profile = {"free_tier_used_at": "2026-04-01T00:00:00+00:00", "is_active": False, "is_beta": False}
    assert _is_user_free_tier(profile) is True
