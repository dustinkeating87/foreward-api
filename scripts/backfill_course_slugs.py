#!/usr/bin/env python3
"""
Idempotent backfill: normalize alert_profiles.courses to canonical slugs.

Usage:
    python scripts/backfill_course_slugs.py          # dry-run (default)
    python scripts/backfill_course_slugs.py --apply  # write to DB

Context:
    Before 2026-05-27 the API accepted raw display names from the frontend, so
    some rows have entries like "Humber Valley Golf Course" instead of
    "humber-valley". All active paying alerts were hotfixed manually; this
    script handles any stragglers and serves as the documented artifact for the
    structural fix tracked in ClickUp 86ahk5w6n.

    The reverse map is derived dynamically from util/courses.py — no hardcoded
    display-name literals. Unknown values are logged and left untouched.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.util.courses import COURSES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _build_reverse_map() -> dict[str, str]:
    """display_name (case-insensitive) → slug."""
    return {v["display_name"].lower(): k for k, v in COURSES.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill alert_profiles.courses to slugs")
    parser.add_argument("--apply", action="store_true", help="Write changes to DB (default: dry-run)")
    args = parser.parse_args()

    from supabase import create_client  # noqa: E402

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        log.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    client = create_client(url, key)
    reverse = _build_reverse_map()
    known_slugs = set(COURSES.keys())

    result = client.table("alert_profiles").select("id, courses, status").execute()
    rows = result.data or []

    changed = 0
    skipped_unknown = 0

    for row in rows:
        courses = row.get("courses") or []
        new_courses = []
        row_changed = False
        row_unknown = []

        for c in courses:
            if c in known_slugs:
                new_courses.append(c)
                continue
            slug = reverse.get(c.lower())
            if slug:
                new_courses.append(slug)
                row_changed = True
                log.info("alert %s: '%s' → '%s'", row["id"][:8], c, slug)
            else:
                new_courses.append(c)
                row_unknown.append(c)

        if row_unknown:
            log.warning("alert %s (status=%s): unresolved values: %s", row["id"][:8], row["status"], row_unknown)
            skipped_unknown += 1

        if row_changed:
            changed += 1
            if args.apply:
                client.table("alert_profiles").update({"courses": new_courses}).eq("id", row["id"]).execute()

    mode = "APPLY" if args.apply else "DRY-RUN"
    log.info("[%s] %d rows would change, %d rows have unresolvable values", mode, changed, skipped_unknown)
    if not args.apply and changed:
        log.info("Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()
