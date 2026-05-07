COURSE_DISPLAY_NAMES: dict[str, str] = {
    # GolfNow courses
    "lakeview":          "Lakeview Golf Course",
    "eagles-nest":       "Eagles Nest Golf Club",
    "royal-woodbine":    "Royal Woodbine Golf Club",
    "angus-glen-north":  "Angus Glen Golf Club - North Course",
    "remington-valley":  "Remington Parkview - Valley Course",
    "remington-upper":   "Remington Parkview - Upper Course",
    "flemingdon-park":   "Flemingdon Park Golf Club",
    "pickering-glen":    "Pickering Glen Golf Club",
    "winchester":        "Winchester Golf Club",
    "braeben":           "BraeBen Golf Course",
    "sandridge-dunes":   "Sandridge Dunes (Vero Beach, FL)",
    "sandridge-lakes":   "Sandridge Lakes (Vero Beach, FL)",
    # Chronogolf courses
    "lionhead-legends":  "Lionhead Golf Club - Legends Course",
    "lionhead-masters":  "Lionhead Golf Club - Masters Course",
    "osprey-heathlands": "TPC Toronto at Osprey Valley - Heathlands",
    "osprey-hoot":       "TPC Toronto at Osprey Valley - Hoot Course",
    "osprey-north":      "TPC Toronto at Osprey Valley - North Course",
    "royal-ashburn":     "Royal Ashburn Golf Club",
    "lakeridge-links":   "Lakeridge Links Golf Club",
    "whispering-ridge":  "Whispering Ridge Golf Club",
    "silver-lakes":      "Silver Lakes Golf & Country Club",
    "bushwood":          "Bushwood Golf Club",
}


def slug_to_display_name(slug: str) -> str:
    """
    Returns human-readable course name for a slug.
    Falls back to title-cased hyphens-to-spaces if slug is unknown.

    Note: scraper fetches canonical names from external APIs at runtime
    (sent_slots.course_name). This dict is hardcoded for email/SMS copy
    where we don't have a sent_slots row to pull from. Periodic reconciliation
    against the scraper's runtime names recommended (~quarterly).
    """
    if slug in COURSE_DISPLAY_NAMES:
        return COURSE_DISPLAY_NAMES[slug]
    return slug.replace("-", " ").replace("_", " ").title()


def courses_to_display_string(slugs: list) -> str:
    """
    Renders a list of course slugs for use in email/SMS copy.
    Single course: returns its display name.
    Multiple: returns "{n} courses you're watching".
    """
    if not slugs:
        return "your alert"
    if len(slugs) == 1:
        return slug_to_display_name(slugs[0])
    return f"{len(slugs)} courses you're watching"
