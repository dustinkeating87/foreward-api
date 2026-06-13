"""
Canonical course key → display name mapping for foreward-api.

alert_profiles.courses stores course keys (slug, e.g. "lakeview"). This module
is the write-time validation gate: any slug not present here is rejected 422.

Display names here must match what the scraper writes to sent_slots.course_name
(case-sensitive) for GolfNow and Chronogolf — authoritative source is
GOLFNOW_COURSES / CHRONOGOLF_COURSES in the scraper files.

GTG display names here are ADVISORY ONLY. The gateway API
(gateway.golfthe6ix.com) is the runtime authority; CourseName in live slots
may differ. Slugs are still canonical and must match exactly.

Keeping this dict in sync with the scraper's course registries is enforced by
CI (foreward-scraper/.github/workflows/check_course_keys.yml).
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
    # ── Batch 1 GTA expansion (2026-05-13) ─────────────────────────────────────
    "deer-creek-golf-club-short-course-9-holes": {"display_name": "Deer Creek Golf Club - Short Course - 9 Holes", "platform": "golfnow"},
    "deer-creek-golf-club-north-course": {"display_name": "Deer Creek Golf Club North Course", "platform": "golfnow"},
    "deer-creek-golf-club-south-course": {"display_name": "Deer Creek Golf Club South Course", "platform": "golfnow"},
    "south-ajax-golf-club-lake-breeze": {"display_name": "South Ajax Golf Club - Lake Breeze", "platform": "golfnow"},
    "south-ajax-golf-club-whistling-wind": {"display_name": "South Ajax Golf Club - Whistling Wind", "platform": "golfnow"},
    "mystic-golf-club": {"display_name": "Mystic Golf Club", "platform": "golfnow"},
    "peel-village-golf-course-9-holes": {"display_name": "Peel Village Golf Course - 9 Holes", "platform": "golfnow"},
    "turnberry-golf-club-ontario": {"display_name": "Turnberry Golf Club - Ontario", "platform": "golfnow"},
    "hidden-lake-new-course": {"display_name": "Hidden Lake - New Course", "platform": "golfnow"},
    "hidden-lake-old-course": {"display_name": "Hidden Lake - Old Course", "platform": "golfnow"},
    "lowville-golf-club": {"display_name": "Lowville Golf Club", "platform": "golfnow"},
    "mount-nemo-golf-club": {"display_name": "Mount Nemo Golf Club", "platform": "golfnow"},
    "tyandaga-golf-course": {"display_name": "Tyandaga Golf Course", "platform": "golfnow"},
    "caistorville-golf-club": {"display_name": "Caistorville Golf Club", "platform": "golfnow"},
    "bantys-roost-golf-country-club": {"display_name": "Banty's Roost Golf & Country Club", "platform": "golfnow"},
    "harbour-view-golf-country-club": {"display_name": "Harbour View Golf & Country Club", "platform": "golfnow"},
    "buncrana-golf-course-par-3": {"display_name": "Buncrana Golf Course - Par 3", "platform": "golfnow"},
    "dragons-fire-golf-club": {"display_name": "Dragon's Fire Golf Club", "platform": "golfnow"},
    "east-wing-golf-course-cardinal-golf-club": {"display_name": "East Wing Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "kettle-creek-golf-course-cardinal-golf-club": {"display_name": "Kettle Creek Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "redcrest-golf-course-cardinal-golf-club": {"display_name": "RedCrest Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "west-wing-golf-course-cardinal-golf-club": {"display_name": "West Wing Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "braeben-golf-country-club-academy-course": {"display_name": "Braeben Golf & Country Club - Academy Course", "platform": "golfnow"},
    "goreway-golf-club": {"display_name": "Goreway Golf Club", "platform": "golfnow"},
    "southern-pines-golf-and-country-club": {"display_name": "Southern Pines Golf and Country Club", "platform": "golfnow"},
    "deerfield-golf-club-on": {"display_name": "Deerfield Golf Club (ON)", "platform": "golfnow"},
    "glen-abbey-golf-club": {"display_name": "Glen Abbey Golf Club", "platform": "golfnow"},
    "harmony-creek-golf-centre": {"display_name": "Harmony Creek Golf Centre", "platform": "golfnow"},
    "oshawa-airport-golf-club": {"display_name": "Oshawa Airport Golf Club", "platform": "golfnow"},
    "cherry-downs": {"display_name": "Cherry Downs", "platform": "golfnow"},
    "spring-creek-golf-club": {"display_name": "Spring Creek Golf Club", "platform": "golfnow"},
    "dunnys-divots": {"display_name": "Dunny's Divots", "platform": "golfnow"},
    "bloomington-downs-golf-club": {"display_name": "Bloomington Downs Golf Club", "platform": "golfnow"},
    "nobleton-lakes-golf-club": {"display_name": "Nobleton Lakes Golf Club", "platform": "golfnow"},
    "shawneeki-golf-club": {"display_name": "Shawneeki Golf Club", "platform": "golfnow"},
    "rolling-hills-bethesda-grange": {"display_name": "Rolling Hills - Bethesda Grange", "platform": "golfnow"},
    "royal-stouffville-executive": {"display_name": "Royal Stouffville Executive", "platform": "golfnow"},
    "royal-stouffville-golf-course": {"display_name": "Royal Stouffville Golf Course", "platform": "golfnow"},
    "foxbridge-golf-course": {"display_name": "Foxbridge Golf Course", "platform": "golfnow"},
    "mill-run-golf-club-highland-course": {"display_name": "Mill Run Golf Club - Highland Course", "platform": "golfnow"},
    "wooden-sticks-golf-club": {"display_name": "Wooden Sticks Golf Club", "platform": "golfnow"},
    "gull-river-golf-club": {"display_name": "Gull River Golf Club", "platform": "golfnow"},
    "uplands-golf-club": {"display_name": "Uplands Golf Club", "platform": "golfnow"},
    "acton-golf-club": {"display_name": "Acton Golf Club", "platform": "chronogolf"},
    "tam-o-shanter-golf-club": {"display_name": "Tam O' Shanter Golf Club", "platform": "chronogolf"},
    "carruthers-creek-golf-centre-whistling-wind": {"display_name": "Carruthers Creek Golf Centre – Whistling Wind", "platform": "chronogolf"},
    "carruthers-creek-golf-centre-lake-breeze": {"display_name": "Carruthers Creek Golf Centre – Lake Breeze", "platform": "chronogolf"},
    "riverside-golf-club-ontario-ajax": {"display_name": "Riverside Golf Club", "platform": "chronogolf"},
    "south-ajax-golf-club": {"display_name": "South Ajax Golf Club", "platform": "chronogolf"},
    "the-deer-creek-academy": {"display_name": "The Deer Creek Academy", "platform": "chronogolf"},
    "knollwood-golf-country-club-the-new-course": {"display_name": "Knollwood Golf & Country Club – The New Course", "platform": "chronogolf"},
    "knollwood-golf-country-club-the-old-course": {"display_name": "Knollwood Golf & Country Club – The Old Course", "platform": "chronogolf"},
    "oak-gables-golf-club-learning-centre": {"display_name": "Oak Gables Golf Club", "platform": "chronogolf"},
    "beacon-hall-golf-club": {"display_name": "Beacon Hall Golf Club", "platform": "chronogolf"},
    "highland-gate-golf-club-ontario--2": {"display_name": "Highland Gate Golf Club", "platform": "chronogolf"},
    "highland-gate-golf-club-ontario": {"display_name": "Highland Gate Golf Club", "platform": "chronogolf"},
    "magna-golf-club": {"display_name": "Magna Golf Club", "platform": "chronogolf"},
    "st-andrews-valley-golf-club": {"display_name": "St. Andrew's Valley Golf Club", "platform": "chronogolf"},
    "westview-golf-club-ontario-aurora-homestead": {"display_name": "Westview Golf Club – Homestead", "platform": "chronogolf"},
    "westview-golf-club-ontario-aurora-middle": {"display_name": "Westview Golf Club – Middle", "platform": "chronogolf"},
    "westview-golf-club-ontario-aurora-lakeland": {"display_name": "Westview Golf Club – Lakeland", "platform": "chronogolf"},
    "southbrook-golf-country-club": {"display_name": "Southbrook Golf & Country Club", "platform": "chronogolf"},
    "ayren-links-golf-club": {"display_name": "Ayren Links Golf Club", "platform": "chronogolf"},
    "bowmanville-golf-country-club": {"display_name": "Bowmanville Golf & Country Club", "platform": "chronogolf"},
    "quarry-lion-golf-resort": {"display_name": "Quarry Lion Golf Resort", "platform": "chronogolf"},
    "stonehenge-golf-club": {"display_name": "Stonehenge Golf Club", "platform": "chronogolf"},
    "bradford-highlands-golf-club": {"display_name": "Bradford Highlands Golf Club", "platform": "chronogolf"},
    "brampton-golf-club": {"display_name": "Brampton Golf Club", "platform": "chronogolf"},
    "castlemore-golf-and-country-club": {"display_name": "Castlemore Golf and Country Club", "platform": "chronogolf"},
    "parkshore-golf-club": {"display_name": "Goreway Golf Club", "platform": "chronogolf"},
    "peel-village-golf-course": {"display_name": "Peel Village Golf Course", "platform": "chronogolf"},
    "riverstone-golf-and-country-club": {"display_name": "Riverstone Golf and Country Club", "platform": "chronogolf"},
    "riverstone-golf-course": {"display_name": "Riverstone Golf Course", "platform": "chronogolf"},
    "turnberry-golf-club": {"display_name": "Turnberry Golf Club", "platform": "chronogolf"},
    "lyndebrook-golf-club": {"display_name": "Lyndebrook Golf Club", "platform": "chronogolf"},
    "winchester-golf-club-ontario-brooklyn": {"display_name": "Winchester Golf Club", "platform": "chronogolf"},
    "burlington-golf-country-club": {"display_name": "Burlington Golf & Country Club", "platform": "chronogolf"},
    "burlington-springs-golf-club": {"display_name": "Burlington Springs Golf Club", "platform": "chronogolf"},
    "camisle-golf-club": {"display_name": "Camisle Golf Club", "platform": "chronogolf"},
    "lowville-heights-golf-club": {"display_name": "Lowville Heights Golf Club", "platform": "chronogolf"},
    "millcroft-golf-club": {"display_name": "Millcroft Golf Club", "platform": "chronogolf"},
    "tyandaga-municipal-golf-course": {"display_name": "Tyandaga Municipal Golf Course", "platform": "chronogolf"},
    "glen-eagle-golf-club": {"display_name": "Glen Eagle Golf Club", "platform": "chronogolf"},
    "legacy-pines-golf-club": {"display_name": "Legacy Pines Golf Club", "platform": "chronogolf"},
    "banty-s-roost-golf-club": {"display_name": "Banty’s Roost Golf Club", "platform": "chronogolf"},
    "carlisle-golf-country-club-north": {"display_name": "Carlisle Golf & Country Club – North", "platform": "chronogolf"},
    "carlisle-golf-country-club-south": {"display_name": "Carlisle Golf & Country Club – South", "platform": "chronogolf"},
    "carlisle-golf-country-club-east": {"display_name": "Carlisle Golf & Country Club – East", "platform": "chronogolf"},
    "pebblestone-golf-course": {"display_name": "Pebblestone Golf Course", "platform": "chronogolf"},
    "flemingdon-park-golf-course": {"display_name": "Flemingdon Park Golf Course", "platform": "chronogolf"},
    "centennial-park-golf-center-north-nine": {"display_name": "Centennial Park Golf Center – North Nine", "platform": "chronogolf"},
    "centennial-park-golf-center-west-nine": {"display_name": "Centennial Park Golf Center – West Nine", "platform": "chronogolf"},
    "centennial-park-golf-center-east-nine": {"display_name": "Centennial Park Golf Center – East Nine", "platform": "chronogolf"},
    "islington-golf-club": {"display_name": "Islington Golf Club", "platform": "chronogolf"},
    "markland-wood-country-club": {"display_name": "Markland Wood Country Club", "platform": "chronogolf"},
    "north-halton-country-club": {"display_name": "North Halton Country Club", "platform": "chronogolf"},
    "harbor-view-golf-country-club": {"display_name": "Harbor View Golf & Country Club", "platform": "chronogolf"},
    "dragon-s-fire-golf-club": {"display_name": "Dragon's Fire Golf Club - DO NOT USE", "platform": "chronogolf"},
    "hornby-glen-golf-course": {"display_name": "Hornby Glen Golf Course", "platform": "chronogolf"},
    "wyldewood-golf-country-club": {"display_name": "Wyldewood Golf & Country Club", "platform": "chronogolf"},
    "carrying-place-country-club": {"display_name": "Carrying Place Country Club", "platform": "chronogolf"},
    "cardinal-golf-club-redcrest": {"display_name": "Cardinal Golf Complex – RedCrest", "platform": "chronogolf"},
    "cardinal-golf-club-east-wing": {"display_name": "Cardinal Golf Complex – East Wing", "platform": "chronogolf"},
    "cardinal-golf-club-west-wing": {"display_name": "Cardinal Golf Complex – West Wing", "platform": "chronogolf"},
    "cardinal-golf-club-kettle-creek": {"display_name": "Cardinal Golf Complex – Kettle Creek", "platform": "chronogolf"},
    "kleinburg-golf-country-club": {"display_name": "Kleinburg Golf & Country Club", "platform": "chronogolf"},
    "kirbylinks-golf-course": {"display_name": "Kirby Links Golf Course", "platform": "chronogolf"},
    "angus-glen-golf-club-south-course": {"display_name": "Angus Glen Golf Club – South Course", "platform": "chronogolf"},
    "angus-glen-golf-club-north-course": {"display_name": "Angus Glen Golf Club – North Course", "platform": "chronogolf"},
    "mandarin-golf-country-club": {"display_name": "Mandarin Golf & Country Club", "platform": "chronogolf"},
    "markham-green-golf-club": {"display_name": "Markham Green Golf Club", "platform": "chronogolf"},
    "royal-ontario-golf-club": {"display_name": "Royal Ontario Golf Club", "platform": "chronogolf"},
    "mississaugua-golf-country-club": {"display_name": "Mississaugua Golf & Country Club", "platform": "chronogolf"},
    "oshawa-golf-and-curling-club": {"display_name": "Oshawa Golf Club", "platform": "chronogolf"},
    "bunker-hill-golf-club": {"display_name": "Bunker Hill Golf Club", "platform": "chronogolf"},
    "pickering-glen-golf-club": {"display_name": "Pickering Glen Golf Club", "platform": "chronogolf"},
    "pickering-golf-club": {"display_name": "Pickering Golf Club", "platform": "chronogolf"},
    "summerlea-golf-club": {"display_name": "Summerlea Golf Club", "platform": "chronogolf"},
    "richmond-hill-golf-club": {"display_name": "Richmond Hill Golf Club", "platform": "chronogolf"},
    "ballantrae-golf-club": {"display_name": "Ballantrae Golf Club", "platform": "chronogolf"},
    "sleepy-hollow-country-club-ontario": {"display_name": "Sleepy Hollow Country Club", "platform": "chronogolf"},
    "bayview-golf-country-club": {"display_name": "Bayview Golf & Country Club", "platform": "chronogolf"},
    "mill-run-golf-club-ontario": {"display_name": "Mill Run Golf Club", "platform": "chronogolf"},
    "eldorado-golf-club": {"display_name": "Eldorado Golf Club", "platform": "chronogolf"},
    # ── Tee-on ───────────────────────────────────────────────────────────────────
    # NS / HRM
    "the-links-at-brunello":      {"display_name": "The Links at Brunello",             "platform": "teeon"},
    "glen-arbour-golf-club":      {"display_name": "Glen Arbour Golf Club",              "platform": "teeon"},
    "airlane-golf-club":          {"display_name": "Airlane Golf Club",                 "platform": "teeon"},
    "fox-hollow-golf-club-ns":    {"display_name": "Fox Hollow Golf Club",              "platform": "teeon"},
    "indian-lake-golf-course":    {"display_name": "Indian Lake Golf Course",           "platform": "teeon"},
    "lost-creek-golf-club":       {"display_name": "Lost Creek Golf Club",              "platform": "teeon"},
    # Ontario / Toronto-area
    "oakville-executive-golf-courses": {"display_name": "Oakville Executive Golf Courses", "platform": "teeon"},
    "pheasant-run-golf-club":     {"display_name": "Pheasant Run Golf Club",             "platform": "teeon"},
    "turtle-creek-golf-club":     {"display_name": "Turtle Creek Golf Club",             "platform": "teeon"},
    # Ontario / Hamilton-area
    "flamborough-hills-golf-club": {"display_name": "Flamborough Hills Golf Club",       "platform": "teeon"},
    "granite-ridge-golf-club":    {"display_name": "Granite Ridge Golf Club",            "platform": "teeon"},
    "copetown-woods-golf-club":   {"display_name": "Copetown Woods Golf Club",           "platform": "teeon"},
    "crosswinds-golf-country-club": {"display_name": "Crosswinds Golf & Country Club",   "platform": "teeon"},
    "willow-valley-golf-course":  {"display_name": "Willow Valley Golf Course",          "platform": "teeon"},
    # ── GTG (display names advisory — gateway API is authoritative at runtime) ─
    "dentonia-park":  {"display_name": "Dentonia Park Golf Course",  "platform": "gtg"},
    "don-valley":     {"display_name": "Don Valley Golf Course",     "platform": "gtg"},
    "humber-valley":  {"display_name": "Humber Valley Golf Course",  "platform": "gtg"},
    "maple-acres":    {"display_name": "Maple Acres Golf Course",    "platform": "gtg"},
    "scarlett-woods": {"display_name": "Scarlett Woods Golf Course", "platform": "gtg"},
    "tam-o-shanter":  {"display_name": "Tam O'Shanter Golf Course",  "platform": "gtg"},
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
