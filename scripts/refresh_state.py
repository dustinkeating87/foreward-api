#!/usr/bin/env python3
"""
refresh_state.py — Refresh docs/STATE.md with live course data from
foreward-scraper and foreward (frontend) repos.

Usage:
    GITHUB_TOKEN=xxx python3 scripts/refresh_state.py
    GITHUB_TOKEN=xxx python3 scripts/refresh_state.py --dry-run
"""

import argparse
import ast
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
STATE_MD = REPO_ROOT / "docs" / "STATE.md"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def clone_repo(url: str, dest: str) -> None:
    """Shallow-clone a repo to dest, suppressing credential echo."""
    subprocess.run(
        ["git", "clone", "--depth=1", url, dest],
        check=True,
        capture_output=True,
    )


def get_sha(repo_dir: str) -> str:
    return (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
        )
        .decode()
        .strip()
    )


def get_self_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(REPO_ROOT),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except subprocess.CalledProcessError:
        return "unknown"


# ---------------------------------------------------------------------------
# AST parsing (Python source — never regex)
# ---------------------------------------------------------------------------


def extract_course_list(source: str, varname: str) -> list[dict]:
    """Extract a top-level list-of-dicts assignment from Python source via AST."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == varname:
                    return ast.literal_eval(node.value)
    raise ValueError(f"{varname} not found in source")


# ---------------------------------------------------------------------------
# Frontend parsing (TypeScript — regex is fine)
# ---------------------------------------------------------------------------


def extract_frontend_courses(ts_source: str) -> tuple[list[dict], list[dict]]:
    """
    Parse GTA_COURSES and BY_REQUEST_COURSES arrays from courses.ts.

    Returns (gta_courses, by_request_courses) where each entry is
    {"key": str, "label": str}.
    """

    def parse_array(array_name: str, source: str) -> list[dict]:
        # Match the full array body between the outermost [ ... ]
        pattern = rf"export\s+const\s+{array_name}[^=]*=\s*\["
        m = re.search(pattern, source)
        if not m:
            return []
        start = m.end() - 1  # position of opening [
        depth = 0
        end = start
        for i, ch in enumerate(source[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        array_body = source[start : end + 1]

        # Extract { key: "...", label: "..." } objects
        entry_re = re.compile(
            r'\{\s*key:\s*"([^"]+)"\s*,\s*label:\s*"([^"]+)"\s*\}'
        )
        return [
            {"key": key, "label": label}
            for key, label in entry_re.findall(array_body)
        ]

    gta = parse_array("GTA_COURSES", ts_source)
    by_request = parse_array("BY_REQUEST_COURSES", ts_source)
    return gta, by_request


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_golfnow(courses: list[dict]) -> list[dict]:
    out = []
    for c in courses:
        name = c["display_name"]
        region = "By Request (FL)" if "Vero Beach" in name else "GTA"
        out.append(
            {
                "key": c["course_key"],
                "name": name,
                "platform": "golfnow",
                "platform_id": str(c["facility_id"]),
                "region": region,
                "active": bool(c.get("active", True)),
            }
        )
    return out


def normalize_chronogolf(courses: list[dict]) -> list[dict]:
    out = []
    for c in courses:
        name = c["display_name"]
        region = "By Request (FL)" if "Vero Beach" in name else "GTA"
        out.append(
            {
                "key": c["course_key"],
                "name": name,
                "platform": "chronogolf",
                "platform_id": str(c["course_id"]),
                "region": region,
                "active": bool(c.get("active", True)),
            }
        )
    return out


def normalize_gtg(courses: list[dict]) -> list[dict]:
    out = []
    for c in courses:
        name = c["display_name"]
        out.append(
            {
                "key": c["course_key"],
                "name": name,
                "platform": "gtg",
                "platform_id": c["course_key"],  # no numeric ID for GTG
                "region": "GTA",
                "active": True,  # GTG has no active field
            }
        )
    return out


# ---------------------------------------------------------------------------
# STATE.md AUTOGEN fence rewriting
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(
    r"(<!-- AUTOGEN:(\w+) -->)(.*?)(<!-- /AUTOGEN:\2 -->)",
    re.DOTALL,
)


def rewrite_autogen(existing: str, sections: dict[str, str]) -> str:
    """
    Replace content between AUTOGEN fences with new content.
    Sections not present in `sections` dict are left unchanged.
    """

    def replacer(m: re.Match) -> str:
        open_fence = m.group(1)
        name = m.group(2)
        close_fence = m.group(4)
        if name in sections:
            return f"{open_fence}\n{sections[name]}\n{close_fence}"
        return m.group(0)

    return FENCE_RE.sub(replacer, existing)


def make_skeleton_state_md(sections: dict[str, str]) -> str:
    """Create a minimal STATE.md when the file doesn't exist yet."""
    parts = ["# Good Lie Golf — State\n"]
    for name, content in sections.items():
        parts.append(f"<!-- AUTOGEN:{name} -->\n{content}\n<!-- /AUTOGEN:{name} -->")
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------


def gen_last_updated(
    api_sha: str, scraper_sha: str, frontend_sha: str
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"_Last refreshed: {ts} UTC_\n\n"
        "| Source | Commit |\n"
        "|--------|--------|\n"
        f"| foreward-api | {api_sha} |\n"
        f"| foreward-scraper | {scraper_sha} |\n"
        f"| foreward (frontend) | {frontend_sha} |"
    )


def gen_course_counts(all_scraper: list[dict]) -> str:
    platforms = ["golfnow", "chronogolf", "gtg"]
    rows = []
    total_total = total_active = total_inactive = 0

    for p in platforms:
        subset = [c for c in all_scraper if c["platform"] == p]
        total = len(subset)
        active = sum(1 for c in subset if c["active"])
        inactive = total - active
        total_total += total
        total_active += active
        total_inactive += inactive
        inactive_str = "—" if p == "gtg" else str(inactive)
        label_map = {"golfnow": "GolfNow", "chronogolf": "Chronogolf", "gtg": "GTG"}
        label = label_map[p]
        rows.append(f"| {label} | {total} | {active} | {inactive_str} |")

    table = (
        "| Platform | Total | Active | Inactive |\n"
        "|----------|-------|--------|----------|\n"
        + "\n".join(rows)
        + f"\n| **Total** | **{total_total}** | **{total_active}** | **{total_inactive}** |"
    )

    # By region
    gta_count = sum(1 for c in all_scraper if c["region"] == "GTA")
    fl_count = sum(1 for c in all_scraper if c["region"] == "By Request (FL)")
    region_table = (
        "\nBy region:\n\n"
        "| Region | Count |\n"
        "|--------|-------|\n"
        f"| GTA | {gta_count} |\n"
        f"| By Request (FL) | {fl_count} |"
    )

    return table + region_table


def gen_courses_by_platform(all_scraper: list[dict]) -> str:
    platforms = [
        ("golfnow", "GolfNow"),
        ("chronogolf", "Chronogolf"),
        ("gtg", "GTG (City of Toronto)"),
    ]
    sections = []
    for p_key, p_label in platforms:
        subset = [c for c in all_scraper if c["platform"] == p_key]
        if not subset:
            continue
        header = f"### {p_label}\n\n"
        header += "| Key | Name | Platform ID | Region | Active |\n"
        header += "|-----|------|-------------|--------|--------|\n"
        rows = []
        for c in sorted(subset, key=lambda x: x["name"]):
            active_str = "yes" if c["active"] else "no"
            rows.append(
                f"| {c['key']} | {c['name']} | {c['platform_id']} | {c['region']} | {active_str} |"
            )
        sections.append(header + "\n".join(rows))
    return "\n\n".join(sections)


def gen_coverage_gaps(
    all_scraper: list[dict],
    gta_frontend: list[dict],
    by_request_frontend: list[dict],
) -> str:
    all_frontend = gta_frontend + by_request_frontend

    # Build lookup sets by normalized display name
    scraper_names = {c["name"].strip().lower(): c for c in all_scraper}
    # Frontend GTA_COURSES use display name as key; BY_REQUEST uses slug key but label is display name
    frontend_names = {f["label"].strip().lower(): f for f in all_frontend}

    scraper_only = [
        c for norm, c in scraper_names.items() if norm not in frontend_names
    ]
    frontend_only = [
        f for norm, f in frontend_names.items() if norm not in scraper_names
    ]

    parts = []

    parts.append("### Scraper-only (not in frontend picker)\n")
    if scraper_only:
        parts.append("| Platform | Key | Name |")
        parts.append("|----------|-----|------|")
        for c in sorted(scraper_only, key=lambda x: x["name"]):
            parts.append(f"| {c['platform']} | {c['key']} | {c['name']} |")
    else:
        parts.append("_None — all scraper courses are in the frontend picker._")

    parts.append("\n### Frontend-only (not in scraper)\n")
    if frontend_only:
        parts.append("| Key | Label |")
        parts.append("|-----|-------|")
        for f in sorted(frontend_only, key=lambda x: x["label"]):
            parts.append(f"| {f['key']} | {f['label']} |")
    else:
        parts.append("_None — all frontend courses are tracked in the scraper._")

    return "\n".join(parts)


def gen_platforms_status() -> str:
    return (
        "| Platform | Status | Scraper File | Notes |\n"
        "|----------|--------|-------------|-------|\n"
        "| GTG | active | tee_sniper.py | City of Toronto municipal courses |\n"
        "| GolfNow | active | golfnow_scraper.py | |\n"
        "| Chronogolf | tracked, not in ALERTING_PLATFORMS | chronogolf_scraper.py | |"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh docs/STATE.md with live course data."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and diff but do not write STATE.md.",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    scraper_url = f"https://x-access-token:{token}@github.com/dustinkeating87/foreward-scraper.git"
    frontend_url = f"https://x-access-token:{token}@github.com/dustinkeating87/foreward.git"

    api_sha = get_self_sha()

    with tempfile.TemporaryDirectory(prefix="refresh_state_") as tmpdir:
        scraper_dir = os.path.join(tmpdir, "foreward-scraper")
        frontend_dir = os.path.join(tmpdir, "foreward")

        # ------------------------------------------------------------------
        # Clone repos
        # ------------------------------------------------------------------
        print("Cloning foreward-scraper…")
        clone_repo(scraper_url, scraper_dir)
        scraper_sha = get_sha(scraper_dir)
        print(f"  foreward-scraper @ {scraper_sha}")

        print("Cloning foreward…")
        clone_repo(frontend_url, frontend_dir)
        frontend_sha = get_sha(frontend_dir)
        print(f"  foreward (frontend) @ {frontend_sha}")

        # ------------------------------------------------------------------
        # Parse scraper sources
        # ------------------------------------------------------------------
        golfnow_path = os.path.join(scraper_dir, "golfnow_scraper.py")
        chronogolf_path = os.path.join(scraper_dir, "chronogolf_scraper.py")
        tee_sniper_path = os.path.join(scraper_dir, "tee_sniper.py")

        golfnow_raw = extract_course_list(
            Path(golfnow_path).read_text(), "GOLFNOW_COURSES"
        )
        chronogolf_raw = extract_course_list(
            Path(chronogolf_path).read_text(), "CHRONOGOLF_COURSES"
        )
        gtg_raw = extract_course_list(
            Path(tee_sniper_path).read_text(), "GTG_COURSES"
        )

        # Zero-course guard
        if len(golfnow_raw) == 0:
            raise RuntimeError("GOLFNOW_COURSES returned 0 courses — aborting.")
        if len(chronogolf_raw) == 0:
            raise RuntimeError("CHRONOGOLF_COURSES returned 0 courses — aborting.")
        if len(gtg_raw) == 0:
            raise RuntimeError("GTG_COURSES returned 0 courses — aborting.")

        # ------------------------------------------------------------------
        # Parse frontend
        # ------------------------------------------------------------------
        courses_ts_path = os.path.join(frontend_dir, "src", "lib", "courses.ts")
        ts_source = Path(courses_ts_path).read_text()
        gta_frontend, by_request_frontend = extract_frontend_courses(ts_source)

        if len(gta_frontend) + len(by_request_frontend) == 0:
            raise RuntimeError("Frontend courses.ts returned 0 courses — aborting.")

        # ------------------------------------------------------------------
        # Normalize
        # ------------------------------------------------------------------
        golfnow_norm = normalize_golfnow(golfnow_raw)
        chronogolf_norm = normalize_chronogolf(chronogolf_raw)
        gtg_norm = normalize_gtg(gtg_raw)
        all_scraper = golfnow_norm + chronogolf_norm + gtg_norm

        # ------------------------------------------------------------------
        # Print counts
        # ------------------------------------------------------------------
        print(f"\nCourse counts:")
        print(f"  GolfNow:    {len(golfnow_norm)} total  ({sum(1 for c in golfnow_norm if c['active'])} active)")
        print(f"  Chronogolf: {len(chronogolf_norm)} total  ({sum(1 for c in chronogolf_norm if c['active'])} active)")
        print(f"  GTG:        {len(gtg_norm)} total  (all active, no flag)")
        print(f"  Frontend GTA_COURSES:        {len(gta_frontend)}")
        print(f"  Frontend BY_REQUEST_COURSES: {len(by_request_frontend)}")

        # ------------------------------------------------------------------
        # Build sections
        # ------------------------------------------------------------------
        sections = {
            "last_updated": gen_last_updated(api_sha, scraper_sha, frontend_sha),
            "course_counts": gen_course_counts(all_scraper),
            "courses_by_platform": gen_courses_by_platform(all_scraper),
            "coverage_gaps": gen_coverage_gaps(
                all_scraper, gta_frontend, by_request_frontend
            ),
            "platforms_status": gen_platforms_status(),
        }

        # ------------------------------------------------------------------
        # Write STATE.md
        # ------------------------------------------------------------------
        if args.dry_run:
            print("\n--dry-run: skipping STATE.md write.")
            print(f"\nScraper SHA:  {scraper_sha}")
            print(f"Frontend SHA: {frontend_sha}")
            print(f"API SHA:      {api_sha}")
            return

        # Read existing file (or create skeleton)
        if STATE_MD.exists():
            existing = STATE_MD.read_text()
            new_content = rewrite_autogen(existing, sections)
        else:
            print(f"\ndocs/STATE.md not found — creating from scratch.")
            STATE_MD.parent.mkdir(parents=True, exist_ok=True)
            new_content = make_skeleton_state_md(sections)

        if STATE_MD.exists() and STATE_MD.read_text() == new_content:
            print("\ndocs/STATE.md is already up to date — no write needed.")
        else:
            STATE_MD.write_text(new_content)
            print(f"\nWrote {STATE_MD}")

        print(f"\nScraper SHA:  {scraper_sha}")
        print(f"Frontend SHA: {frontend_sha}")
        print(f"API SHA:      {api_sha}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
