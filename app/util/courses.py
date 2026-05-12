"""
Canonical course key → display name mapping for foreward-api.

alert_profiles.courses stores course keys (e.g. "lakeview").
sent_slots.course_name stores display names written by the scraper
(e.g. "Lakeview Golf Course"). This module is the single source of truth
for translating between them within foreward-api.

Display names here MUST match what the scraper writes to sent_slots.course_name
exactly (case-sensitive), otherwise fired_alerts_30d counts in /admin/course-demand
will be wrong. The authoritative source is the display_name field in
GOLFNOW_COURSES (golfnow_scraper.py) and CHRONOGOLF_COURSES (chronogolf_scraper.py).

GTG courses are NOT in this mapping — their CourseName comes from the GTG
gateway API at runtime. Lookups for unknown keys fall back to the raw key.

Keeping this dict in sync with the scraper is manual discipline for now.
Long-term plan: move to a shared Supabase courses table (see ARCHITECTURE.md).
"""

from typing import Optional

# Ordered by platform. Keep in sync with the scraper's internal registries.
COURSES: dict[str, dict[str, str]] = {
    # ── GolfNow ──────────────────────────────────────────────────────────────
    "lakeview":          {"display_name": "Lakeview Golf Course",                      "platform": "golfnow"},
    "braeben":           {"display_name": "BraeBen Golf Course",                       "platform": "golfnow"},
    "eagles-nest":       {"display_name": "Eagles Nest Golf Club",                     "platform": "golfnow"},
    "royal-woodbine":    {"display_name": "Royal Woodbine Golf Club",                  "platform": "golfnow"},
    "angus-glen-north":  {"display_name": "Angus Glen Golf Club – North Course",  "platform": "golfnow"},
    "remington-valley":  {"display_name": "Remington Parkview – Valley Course",   "platform": "golfnow"},
    "remington-upper":   {"display_name": "Remington Parkview – Upper Course",    "platform": "golfnow"},
    "flemingdon-park":   {"display_name": "Flemingdon Park Golf Club",                 "platform": "golfnow"},
    "pickering-glen":    {"display_name": "Pickering Glen Golf Club",                  "platform": "golfnow"},
    "winchester":        {"display_name": "Winchester Golf Club",                      "platform": "golfnow"},
    "sandridge-dunes":   {"display_name": "Sandridge Dunes (Vero Beach, FL)",          "platform": "golfnow"},
    "sandridge-lakes":   {"display_name": "Sandridge Lakes (Vero Beach, FL)",          "platform": "golfnow"},
    # ── Chronogolf ───────────────────────────────────────────────────────────
    "lionhead-legends":  {"display_name": "Lionhead Golf Club – Legends Course",  "platform": "chronogolf"},
    "lionhead-masters":  {"display_name": "Lionhead Golf Club – Masters Course",  "platform": "chronogolf"},
    "osprey-heathlands": {"display_name": "TPC Toronto at Osprey Valley – Heathlands", "platform": "chronogolf"},
    "osprey-hoot":       {"display_name": "TPC Toronto at Osprey Valley – Hoot Course", "platform": "chronogolf"},
    "osprey-north":      {"display_name": "TPC Toronto at Osprey Valley – North Course", "platform": "chronogolf"},
    "royal-ashburn":     {"display_name": "Royal Ashburn Golf Club",                   "platform": "chronogolf"},
    "lakeridge-links":   {"display_name": "Lakeridge Links Golf Club",                 "platform": "chronogolf"},
    "whispering-ridge":  {"display_name": "Whispering Ridge Golf Club",                "platform": "chronogolf"},
    "silver-lakes":      {"display_name": "Silver Lakes Golf & Country Club",          "platform": "chronogolf"},
    "bushwood":          {"display_name": "Bushwood Golf Club",                        "platform": "chronogolf"},
}


def display_name(key: str) -> str:
    """Return display name for a course key, or the key itself if unknown."""
    entry = COURSES.get(key)
    return entry["display_name"] if entry else key


def course_platform(key: str) -> Optional[str]:
    """Return platform for a course key, or None if unknown."""
    entry = COURSES.get(key)
    return entry["platform"] if entry else None


def all_keys() -> list[str]:
    """All known course keys."""
    return list(COURSES.keys())


def all_courses() -> list[dict]:
    """All courses as {key, display_name, platform} dicts."""
    return [
        {"key": k, "display_name": v["display_name"], "platform": v["platform"]}
        for k, v in COURSES.items()
    ]
