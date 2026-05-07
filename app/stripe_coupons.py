import time
import logging
import stripe
from app.config import settings

log = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key


def create_one_time_coupon(user_id: str, coupon_id: str) -> str:
    """
    Generate a single-use Stripe PromotionCode tied to coupon_id.
    coupon_id is the underlying Stripe Coupon ID (e.g. "FREE50PCT"),
    configured once in the Stripe dashboard in Block 4.
    Returns the human-readable promo code string (e.g. "ABCD1234").
    """
    expires_at = int(time.time()) + 7 * 24 * 3600  # 7 days from now
    promo = stripe.PromotionCode.create(
        coupon=coupon_id,
        max_redemptions=1,
        expires_at=expires_at,
        metadata={"supabase_user_id": user_id},
    )
    log.info("stripe_coupon: created promo_code=%s for user=%s", promo.code, user_id[:8])
    return promo.code
