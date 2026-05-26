import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.database import supabase_admin
from app.email import send_idle_nudge_email

log = logging.getLogger(__name__)

NUDGE_DELAY_DAYS = 4
LOOP_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


async def run_idle_nudge() -> None:
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=NUDGE_DELAY_DAYS)).isoformat()

        candidates_result = await asyncio.to_thread(
            lambda: supabase_admin.table("user_profiles")
                .select("id, email, notify_email")
                .lt("created_at", cutoff)
                .neq("is_active", True)
                .neq("is_beta", True)
                .is_("idle_nudge_sent_at", "null")
                .execute()
        )
        candidates = candidates_result.data or []
        if not candidates:
            log.info("idle_nudge: no candidates")
            return

        # One query for all user_ids that have at least one alert
        alerted_result = await asyncio.to_thread(
            lambda: supabase_admin.table("alert_profiles")
                .select("user_id")
                .execute()
        )
        alerted_ids = {row["user_id"] for row in (alerted_result.data or []) if row.get("user_id")}

        targets = [u for u in candidates if u["id"] not in alerted_ids]
        log.info("idle_nudge: %d candidate(s), %d with no alerts", len(candidates), len(targets))

        now_iso = datetime.now(timezone.utc).isoformat()
        for user in targets:
            to = user.get("notify_email") or user.get("email")
            if not to:
                log.info("idle_nudge: skipping user %s — no reachable email", user["id"])
                continue
            try:
                await asyncio.to_thread(lambda addr=to: send_idle_nudge_email(addr))
                await asyncio.to_thread(
                    lambda uid=user["id"]: supabase_admin.table("user_profiles")
                        .update({"idle_nudge_sent_at": now_iso})
                        .eq("id", uid)
                        .execute()
                )
                log.info("idle_nudge: sent to user %s", user["id"])
            except Exception:
                log.exception("idle_nudge: failed for user %s", user["id"])
    except Exception:
        log.exception("idle_nudge: run_idle_nudge error")


async def idle_nudge_loop() -> None:
    await run_idle_nudge()
    while True:
        try:
            await asyncio.sleep(LOOP_INTERVAL_SECONDS)
            await run_idle_nudge()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("idle_nudge_loop iteration failed")
