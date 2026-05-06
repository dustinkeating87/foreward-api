import asyncio
import logging
import os
from datetime import datetime, timezone

from app.database import supabase_admin
from app.email import send_heartbeat_alarm_email, send_heartbeat_recovery_email

log = logging.getLogger(__name__)

THRESHOLD = int(os.environ.get("HEARTBEAT_STALE_THRESHOLD_SECONDS", "120"))


async def check_heartbeat_staleness() -> None:
    try:
        result = await asyncio.to_thread(
            lambda: supabase_admin.table("scraper_health")
                .select("last_heartbeat, heartbeat_alarm_active")
                .eq("id", 1)
                .maybe_single()
                .execute()
        )
        row = (result.data if result else None) or {}
        last_hb = row.get("last_heartbeat")
        alarm_active = bool(row.get("heartbeat_alarm_active", False))

        if not last_hb:
            return

        last_dt = datetime.fromisoformat(last_hb.replace("Z", "+00:00"))
        seconds_stale = int((datetime.now(timezone.utc) - last_dt).total_seconds())
        is_stale = seconds_stale >= THRESHOLD

        if is_stale and not alarm_active:
            update_result = await asyncio.to_thread(
                lambda: supabase_admin.table("scraper_health")
                    .update({"heartbeat_alarm_active": True})
                    .eq("id", 1).eq("heartbeat_alarm_active", False)
                    .execute()
            )
            if update_result.data:
                await asyncio.to_thread(lambda: send_heartbeat_alarm_email(seconds_stale, THRESHOLD))
                log.warning("heartbeat alarm fired: stale=%ds threshold=%ds", seconds_stale, THRESHOLD)
        elif not is_stale and alarm_active:
            update_result = await asyncio.to_thread(
                lambda: supabase_admin.table("scraper_health")
                    .update({"heartbeat_alarm_active": False})
                    .eq("id", 1).eq("heartbeat_alarm_active", True)
                    .execute()
            )
            if update_result.data:
                await asyncio.to_thread(lambda: send_heartbeat_recovery_email(seconds_stale, THRESHOLD))
                log.info("heartbeat recovery sent: now %ds stale (threshold=%ds)", seconds_stale, THRESHOLD)
    except Exception:
        log.exception("check_heartbeat_staleness error")


async def heartbeat_monitor_loop() -> None:
    while True:
        try:
            await asyncio.sleep(60)
            await check_heartbeat_staleness()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("heartbeat_monitor_loop iteration failed")
