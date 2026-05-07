import time
import logging
from fastapi import APIRouter, HTTPException
from app.database import supabase_admin
from app.config import settings

router = APIRouter(tags=["courses"])
log = logging.getLogger(__name__)

_courses_cache: dict = {"data": None, "ts": 0.0}
_CACHE_TTL = 60.0


def _require_free_tier() -> None:
    if not settings.free_tier_enabled:
        raise HTTPException(status_code=503, detail="Free tier is not yet available.")


@router.get("/courses/available-for-free-tier")
def available_free_tier_courses():
    _require_free_tier()

    now = time.monotonic()
    if _courses_cache["data"] is not None and now - _courses_cache["ts"] < _CACHE_TTL:
        return _courses_cache["data"]

    result = supabase_admin.table("alert_profiles") \
        .select("courses") \
        .eq("status", "active") \
        .eq("is_free_tier", False) \
        .execute()

    course_set: set[str] = set()
    for row in result.data or []:
        for course in (row.get("courses") or []):
            course_set.add(course)

    data = {
        "courses": sorted(course_set),
        "count": len(course_set),
        "available": len(course_set) > 0,
    }
    _courses_cache["data"] = data
    _courses_cache["ts"] = now
    log.debug("available_free_tier_courses: %d courses cached", len(course_set))
    return data
