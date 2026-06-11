import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.database import supabase_admin
from app.email import send_paywall_email

log = logging.getLogger(__name__)

FIRE_DELAY_HOURS = 24
LOOP_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


async def run_conversion_sweep(*, dry_run: bool = False) -> None:
    """Send one-time conversion email to free-tier users whose alert fired but haven't subscribed."""
    if not settings.free_tier_enabled:
        log.info("conversion_sweep: FREE_TIER_ENABLED=false — skipping")
        return
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=FIRE_DELAY_HOURS)).isoformat()

        candidates_result = await asyncio.to_thread(
            lambda: supabase_admin.table("user_profiles")
                .select("id, notify_email, email")
                .not_.is_("free_tier_used_at", "null")
                .neq("is_active", True)
                .neq("is_beta", True)
                .is_("paywall_email_sent_at", "null")
                .lt("free_tier_used_at", cutoff)
                .execute()
        )
        candidates = candidates_result.data or []
        log.info(
            "conversion_sweep: %d candidate(s)%s",
            len(candidates),
            " [DRY RUN — no sends]" if dry_run else "",
        )

        if not candidates:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        for user in candidates:
            to = user.get("notify_email") or user.get("email")
            if not to:
                # Fall back to auth.users.email (same pattern as /export-alerts)
                try:
                    resp = await asyncio.to_thread(
                        lambda uid=user["id"]: supabase_admin.auth.admin.get_user_by_id(uid)
                    )
                    if resp and resp.user:
                        to = resp.user.email
                except Exception:
                    pass
            if not to:
                log.info("conversion_sweep: skipping user %s — no reachable email", user["id"])
                continue

            if dry_run:
                log.info("conversion_sweep DRY RUN: would send to %s (user %s)", to, user["id"][:8])
                continue

            try:
                await asyncio.to_thread(lambda addr=to: send_paywall_email(addr))
                await asyncio.to_thread(
                    lambda uid=user["id"]: supabase_admin.table("user_profiles")
                        .update({"paywall_email_sent_at": now_iso})
                        .eq("id", uid)
                        .execute()
                )
                log.info("conversion_sweep: sent to user %s", user["id"][:8])
            except Exception:
                log.exception("conversion_sweep: failed for user %s", user["id"])
    except Exception:
        log.exception("conversion_sweep: run error")


async def conversion_sweep_loop() -> None:
    await run_conversion_sweep()
    while True:
        try:
            await asyncio.sleep(LOOP_INTERVAL_SECONDS)
            await run_conversion_sweep()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("conversion_sweep_loop iteration failed")
