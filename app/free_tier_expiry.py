import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.database import supabase_admin
from app.email import send_final_expiry_email, send_free_tier_expiry_email
from app.stripe_coupons import create_one_time_coupon
from app.util.dates import _parse_iso

log = logging.getLogger(__name__)


async def check_free_tier_expiry() -> None:
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        result = await asyncio.to_thread(
            lambda: supabase_admin.table("alert_profiles")
            .select("id, user_id, renewals_used, polling_expires_at")
            .eq("is_free_tier", True)
            .eq("status", "active")
            .is_("expiry_state", "null")
            .lt("polling_expires_at", now_iso)
            .execute()
        )

        alerts = result.data or []
        if not alerts:
            return

        log.info("free_tier_expiry: %d alert(s) to process", len(alerts))

        for alert in alerts:
            alert_id = alert["id"]
            user_id = alert["user_id"]
            renewals_used = alert.get("renewals_used") or 0

            # Skip if user has since subscribed — don't expire a paying customer's alert
            profile_check = await asyncio.to_thread(
                lambda uid=user_id: supabase_admin.table("user_profiles")
                .select("is_active, is_beta")
                .eq("id", uid)
                .maybe_single()
                .execute()
            )
            p = profile_check.data or {}
            if p.get("is_active") or p.get("is_beta"):
                log.info("free_tier_expiry: skip alert=%s — user converted to paid", alert_id)
                continue

            if renewals_used < 2:
                await _transition_pending_renewal(alert_id, user_id, renewals_used, now_iso)
            else:
                await _transition_final_expired(alert_id, user_id, now_iso)

    except Exception:
        log.exception("check_free_tier_expiry error")


async def _transition_pending_renewal(
    alert_id: str, user_id: str, renewals_used: int, now_iso: str
) -> None:
    try:
        await asyncio.to_thread(
            lambda aid=alert_id: supabase_admin.table("alert_profiles")
            .update({"expiry_state": "expired_pending_renewal", "status": "expired"})
            .eq("id", aid)
            .execute()
        )

        profile_result = await asyncio.to_thread(
            lambda uid=user_id: supabase_admin.table("user_profiles")
            .select("notify_email, email")
            .eq("id", uid)
            .maybe_single()
            .execute()
        )
        profile = profile_result.data or {}
        to_email = profile.get("notify_email") or profile.get("email")

        if to_email:
            renewal_link = f"{settings.frontend_url}/alerts/{alert_id}/renew"
            try:
                await asyncio.to_thread(
                    lambda e=to_email, aid=alert_id, r=renewals_used, lnk=renewal_link:
                        send_free_tier_expiry_email(e, aid, r, lnk)
                )
            except Exception as exc:
                log.error("free_tier_expiry: renewal email failed alert=%s — %s", alert_id, exc)

        log.info(
            "free_tier_expiry: alert=%s → expired_pending_renewal renewals_used=%d",
            alert_id,
            renewals_used,
        )
    except Exception:
        log.exception("free_tier_expiry: _transition_pending_renewal failed alert=%s", alert_id)


async def _transition_final_expired(alert_id: str, user_id: str, now_iso: str) -> None:
    try:
        await asyncio.to_thread(
            lambda aid=alert_id, ts=now_iso: supabase_admin.table("alert_profiles")
            .update({"expiry_state": "final_expired", "final_expired_at": ts, "status": "expired"})
            .eq("id", aid)
            .execute()
        )

        await asyncio.to_thread(
            lambda uid=user_id, ts=now_iso: supabase_admin.table("user_profiles")
            .update({"final_expired_at": ts})
            .eq("id", uid)
            .execute()
        )

        # Generate Stripe promo code — skipped if STRIPE_FREE_TIER_COUPON_ID not configured (Block 4 sets it)
        discount_code: Optional[str] = None
        coupon_id = settings.stripe_free_tier_coupon_id
        if coupon_id:
            try:
                discount_code = await asyncio.to_thread(
                    lambda uid=user_id, cid=coupon_id: create_one_time_coupon(uid, cid)
                )
            except Exception as exc:
                log.error("free_tier_expiry: stripe coupon failed alert=%s — %s", alert_id, exc)
        else:
            log.info("free_tier_expiry: STRIPE_FREE_TIER_COUPON_ID not set — skipping coupon for alert=%s", alert_id)

        profile_result = await asyncio.to_thread(
            lambda uid=user_id: supabase_admin.table("user_profiles")
            .select("notify_email, email")
            .eq("id", uid)
            .maybe_single()
            .execute()
        )
        profile = profile_result.data or {}
        to_email = profile.get("notify_email") or profile.get("email")

        if to_email:
            try:
                await asyncio.to_thread(
                    lambda e=to_email, d=discount_code: send_final_expiry_email(e, d)
                )
            except Exception as exc:
                log.error("free_tier_expiry: final email failed alert=%s — %s", alert_id, exc)

        log.info(
            "free_tier_expiry: alert=%s user=%s → final_expired coupon=%s",
            alert_id,
            user_id[:8],
            discount_code,
        )
    except Exception:
        log.exception("free_tier_expiry: _transition_final_expired failed alert=%s", alert_id)


async def free_tier_expiry_loop() -> None:
    while True:
        try:
            await asyncio.sleep(300)  # 5 minutes — sleep first, then check
            await check_free_tier_expiry()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("free_tier_expiry_loop iteration failed")
