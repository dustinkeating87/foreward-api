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
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
STATE_MD = REPO_ROOT / "docs" / "STATE.md"
COURSES_JSON = REPO_ROOT / "docs" / "courses.json"
ADMIN_PY = REPO_ROOT / "app" / "routers" / "admin.py"


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


def extract_list_constant(source: str, varname: str) -> list:
    """Extract a top-level list assignment from Python source via AST."""
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
    Parse RAW_COURSES and BY_REQUEST_COURSES arrays from courses.ts.
    Returns (main_courses, by_request_courses) where each entry is {"key", "label", "region"}.
    """

    def parse_array(array_name: str, source: str) -> list[dict]:
        # Match both exported and non-exported const declarations (RAW_COURSES is not exported)
        pattern = rf"(?:export\s+)?const\s+{array_name}[^=]*=\s*\["
        m = re.search(pattern, source)
        if not m:
            return []
        start = m.end() - 1
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
        entry_re = re.compile(
            r'\{\s*key:\s*"([^"]+)"\s*,\s*label:\s*"([^"]+)"\s*,\s*region:\s*"([^"]+)"\s*\}'
        )
        return [{"key": k, "label": l, "region": r} for k, l, r in entry_re.findall(array_body)]

    return parse_array("RAW_COURSES", ts_source), parse_array("BY_REQUEST_COURSES", ts_source)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_golfnow(courses: list[dict]) -> list[dict]:
    out = []
    for c in courses:
        name = c["display_name"]
        out.append({
            "key": c["course_key"],
            "name": name,
            "platform": "golfnow",
            "platform_id": str(c["facility_id"]),
            "region": "By Request (FL)" if "Vero Beach" in name else "GTA",
            "course_active": bool(c.get("active", True)),
        })
    return out


def normalize_chronogolf(courses: list[dict]) -> list[dict]:
    out = []
    for c in courses:
        name = c["display_name"]
        out.append({
            "key": c["course_key"],
            "name": name,
            "platform": "chronogolf",
            "platform_id": str(c["course_id"]),
            "region": "By Request (FL)" if "Vero Beach" in name else "GTA",
            "course_active": bool(c.get("active", True)),
        })
    return out


def normalize_gtg(courses: list[dict]) -> list[dict]:
    out = []
    for c in courses:
        out.append({
            "key": c["course_key"],
            "name": c["display_name"],
            "platform": "gtg",
            "platform_id": c["course_key"],
            "region": "GTA",
            "course_active": True,  # GTG has no active field
        })
    return out


def apply_platform_status(courses: list[dict], alerting_platforms: set[str]) -> list[dict]:
    """Annotate each course with platform_active and effective_active."""
    for c in courses:
        c["platform_active"] = c["platform"] in alerting_platforms
        c["effective_active"] = c["course_active"] and c["platform_active"]
    return courses


def active_str(c: dict) -> str:
    if not c["platform_active"]:
        return "no (platform dormant)"
    return "yes" if c["course_active"] else "no"


# ---------------------------------------------------------------------------
# Name normalization for duplicate detection
# ---------------------------------------------------------------------------


def norm_name(name: str) -> str:
    """Lowercase, strip punctuation and extra spaces for fuzzy matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", name.lower())).strip()


# ---------------------------------------------------------------------------
# STATE.md AUTOGEN fence rewriting
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(
    r"(<!-- AUTOGEN:(\w+) -->)(.*?)(<!-- /AUTOGEN:\2 -->)",
    re.DOTALL,
)


def rewrite_autogen(existing: str, sections: dict[str, str]) -> str:
    def replacer(m: re.Match) -> str:
        open_fence, name, _, close_fence = m.group(1), m.group(2), m.group(3), m.group(4)
        if name in sections:
            return f"{open_fence}\n{sections[name]}\n{close_fence}"
        return m.group(0)
    return FENCE_RE.sub(replacer, existing)


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------


def gen_headline_counts(
    all_scraper: list[dict],
    gta_frontend: list[dict],
    by_request_frontend: list[dict],
    alerting_platforms: set[str],
) -> str:
    total_scraper = len(all_scraper)
    total_effective = sum(1 for c in all_scraper if c["effective_active"])
    total_frontend = len(gta_frontend) + len(by_request_frontend)

    # Active-platform gap: on an active platform, course_active=True, not in frontend by name
    frontend_norm = {norm_name(f["label"]) for f in gta_frontend + by_request_frontend}
    active_gap = sum(
        1 for c in all_scraper
        if c["platform_active"] and c["course_active"]
        and norm_name(c["name"]) not in frontend_norm
    )

    return (
        f"| Metric | Count |\n"
        f"|--------|-------|\n"
        f"| Courses in scraper code | {total_scraper} |\n"
        f"| Active (on ALERTING_PLATFORMS, course enabled) | {total_effective} |\n"
        f"| Exposed in frontend picker | {total_frontend} |\n"
        f"| Active-platform gap (scraper active, not in picker) | {active_gap} |"
    )


def gen_last_updated(api_sha: str, scraper_sha: str, frontend_sha: str) -> str:
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
    platform_order = ["golfnow", "chronogolf", "gtg"]
    label_map = {"golfnow": "GolfNow", "chronogolf": "Chronogolf", "gtg": "GTG"}
    rows = []
    total_total = total_active = total_inactive = 0

    for p in platform_order:
        subset = [c for c in all_scraper if c["platform"] == p]
        total = len(subset)
        active = sum(1 for c in subset if c["effective_active"])
        inactive = total - active
        total_total += total
        total_active += active
        total_inactive += inactive
        inactive_str = "—" if p == "gtg" else str(inactive)
        rows.append(f"| {label_map[p]} | {total} | {active} | {inactive_str} |")

    table = (
        "| Platform | Total | Active | Inactive |\n"
        "|----------|-------|--------|----------|\n"
        + "\n".join(rows)
        + f"\n| **Total** | **{total_total}** | **{total_active}** | **{total_inactive}** |"
    )

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
        rows = [
            f"| {c['key']} | {c['name']} | {c['platform_id']} | {c['region']} | {active_str(c)} |"
            for c in sorted(subset, key=lambda x: x["name"])
        ]
        sections.append(header + "\n".join(rows))
    return "\n\n".join(sections)


def gen_coverage_gaps(
    all_scraper: list[dict],
    gta_frontend: list[dict],
    by_request_frontend: list[dict],
) -> str:
    all_frontend = gta_frontend + by_request_frontend
    frontend_norm = {norm_name(f["label"]): f for f in all_frontend}
    scraper_by_norm = {norm_name(c["name"]): c for c in all_scraper}

    # Partition scraper-only entries
    scraper_only = [c for nn, c in scraper_by_norm.items() if nn not in frontend_norm]
    active_gaps = [c for c in scraper_only if c["platform_active"] and c["course_active"]]
    dormant_entries = [c for c in scraper_only if not c["platform_active"] or not c["course_active"]]

    # Frontend-only
    frontend_only = [f for nn, f in frontend_norm.items() if nn not in scraper_by_norm]

    parts = []

    parts.append("### Active-platform gaps (scraper active, not in frontend picker)\n")
    if active_gaps:
        parts.append("| Platform | Key | Name |")
        parts.append("|----------|-----|------|")
        for c in sorted(active_gaps, key=lambda x: x["name"]):
            parts.append(f"| {c['platform']} | {c['key']} | {c['name']} |")
    else:
        parts.append("_None — all active-platform courses are in the frontend picker._")

    parts.append("\n### Dormant-platform / disabled entries (informational)\n")
    if dormant_entries:
        parts.append("| Platform | Key | Name | Reason |")
        parts.append("|----------|-----|------|--------|")
        for c in sorted(dormant_entries, key=lambda x: x["name"]):
            reason = "platform dormant" if not c["platform_active"] else "course disabled in scraper"
            parts.append(f"| {c['platform']} | {c['key']} | {c['name']} | {reason} |")
    else:
        parts.append("_None._")

    parts.append("\n### Frontend-only (in picker but not in scraper)\n")
    if frontend_only:
        parts.append("| Key | Label |")
        parts.append("|-----|-------|")
        for f in sorted(frontend_only, key=lambda x: x["label"]):
            parts.append(f"| {f['key']} | {f['label']} |")
    else:
        parts.append("_None — all frontend courses are tracked in the scraper._")

    return "\n".join(parts)


def gen_cross_platform_duplicates(all_scraper: list[dict]) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in all_scraper:
        groups[norm_name(c["name"])].append(c)

    dupes = {
        nn: courses for nn, courses in groups.items()
        if len({c["platform"] for c in courses}) > 1
    }

    if not dupes:
        return "_No cross-platform duplicates detected._"

    rows = []
    for nn, courses in sorted(dupes.items()):
        platforms = sorted({c["platform"] for c in courses})
        keys = ", ".join(c["key"] for c in sorted(courses, key=lambda x: x["platform"]))
        active_pf = sorted({c["platform"] for c in courses if c["platform_active"]})
        display_name = courses[0]["name"]
        rows.append(
            f"| {display_name} | {', '.join(platforms)} | {keys} | {', '.join(active_pf) or '—'} |"
        )

    return (
        "| Name | Platforms | Keys | Active Platforms |\n"
        "|------|-----------|------|------------------|\n"
        + "\n".join(rows)
    )


def gen_platforms_status(alerting_platforms: set[str]) -> str:
    all_platforms = [
        ("gtg",        "GTG",        "tee_sniper.py",        "City of Toronto municipal courses"),
        ("golfnow",    "GolfNow",    "golfnow_scraper.py",   ""),
        ("chronogolf", "Chronogolf", "chronogolf_scraper.py", "Polled when user alerts target Chronogolf courses; none configured to date"),
    ]
    rows = []
    for p_key, p_label, p_file, p_note in all_platforms:
        status = "in ALERTING_PLATFORMS" if p_key in alerting_platforms else "not in ALERTING_PLATFORMS"
        rows.append(f"| {p_label} | {status} | {p_file} | {p_note} |")
    return (
        "| Platform | Status | Scraper File | Notes |\n"
        "|----------|--------|-------------|-------|\n"
        + "\n".join(rows)
    )


# ---------------------------------------------------------------------------
# courses.json emitter
# ---------------------------------------------------------------------------


def emit_courses_json(
    all_scraper: list[dict],
    api_sha: str,
    scraper_sha: str,
    frontend_sha: str,
) -> None:
    """Write docs/courses.json — canonical machine-readable course list."""
    courses = [
        {
            "key": c["key"],
            "name": c["name"],
            "platform": c["platform"],
            "platform_id": c["platform_id"],
            "active": c["course_active"],
        }
        for c in all_scraper
        if c["platform_active"]
    ]
    courses.sort(key=lambda c: (c["name"].lower(), c["key"]))

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit_shas": {
            "foreward_api": api_sha,
            "foreward_scraper": scraper_sha,
            "foreward": frontend_sha,
        },
        "courses": courses,
    }

    COURSES_JSON.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")

    total = len(courses)
    print(f"\nWrote {COURSES_JSON} ({total} courses)")

    per_platform = {}
    for p in ["golfnow", "chronogolf", "gtg"]:
        per_platform[p] = sum(1 for c in courses if c["platform"] == p)
    print(f"  golfnow={per_platform['golfnow']}  chronogolf={per_platform['chronogolf']}  gtg={per_platform['gtg']}")

    if courses:
        print("\nFirst 5 (alphabetical by name):")
        for c in courses[:5]:
            print(f"  [{c['platform']}] {c['name']}  ({c['key']})")
        print("Last 5:")
        for c in courses[-5:]:
            print(f"  [{c['platform']}] {c['name']}  ({c['key']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh docs/STATE.md with live course data.")
    parser.add_argument("--dry-run", action="store_true", help="Parse but do not write STATE.md.")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # Parse ALERTING_PLATFORMS from local admin.py (authoritative source)
    alerting_platforms: set[str] = set(
        extract_list_constant(ADMIN_PY.read_text(), "ALERTING_PLATFORMS")
    )
    print(f"ALERTING_PLATFORMS: {sorted(alerting_platforms)}")

    api_sha = get_self_sha()

    scraper_url  = f"https://x-access-token:{token}@github.com/dustinkeating87/foreward-scraper.git"
    frontend_url = f"https://x-access-token:{token}@github.com/dustinkeating87/foreward.git"

    with tempfile.TemporaryDirectory(prefix="refresh_state_") as tmpdir:
        scraper_dir  = os.path.join(tmpdir, "foreward-scraper")
        frontend_dir = os.path.join(tmpdir, "foreward")

        print("Cloning foreward-scraper…")
        clone_repo(scraper_url, scraper_dir)
        scraper_sha = get_sha(scraper_dir)
        print(f"  foreward-scraper @ {scraper_sha}")

        print("Cloning foreward…")
        clone_repo(frontend_url, frontend_dir)
        frontend_sha = get_sha(frontend_dir)
        print(f"  foreward (frontend) @ {frontend_sha}")

        # Parse scraper sources
        tee_sniper_path   = os.path.join(scraper_dir, "tee_sniper.py")
        golfnow_path      = os.path.join(scraper_dir, "golfnow_scraper.py")
        chronogolf_path   = os.path.join(scraper_dir, "chronogolf_scraper.py")

        golfnow_raw    = extract_list_constant(Path(golfnow_path).read_text(),    "GOLFNOW_COURSES")
        chronogolf_raw = extract_list_constant(Path(chronogolf_path).read_text(), "CHRONOGOLF_COURSES")
        gtg_raw        = extract_list_constant(Path(tee_sniper_path).read_text(), "GTG_COURSES")

        if not golfnow_raw:
            raise RuntimeError("GOLFNOW_COURSES returned 0 courses — aborting.")
        if not chronogolf_raw:
            raise RuntimeError("CHRONOGOLF_COURSES returned 0 courses — aborting.")
        if not gtg_raw:
            raise RuntimeError("GTG_COURSES returned 0 courses — aborting.")

        # Parse frontend
        ts_source = Path(os.path.join(frontend_dir, "src", "lib", "courses.ts")).read_text()
        gta_frontend, by_request_frontend = extract_frontend_courses(ts_source)

        total_frontend = len(gta_frontend) + len(by_request_frontend)
        print(f"Frontend parsed: {total_frontend} courses found in src/lib/courses.ts")

        if not gta_frontend and not by_request_frontend:
            raise RuntimeError("Frontend courses.ts returned 0 courses — aborting.")

        # Normalize and annotate with platform status
        all_scraper = apply_platform_status(
            normalize_golfnow(golfnow_raw)
            + normalize_chronogolf(chronogolf_raw)
            + normalize_gtg(gtg_raw),
            alerting_platforms,
        )

        print(f"\nCourse counts:")
        for p, label in [("golfnow", "GolfNow"), ("chronogolf", "Chronogolf"), ("gtg", "GTG")]:
            subset = [c for c in all_scraper if c["platform"] == p]
            eff = sum(1 for c in subset if c["effective_active"])
            print(f"  {label}: {len(subset)} total  ({eff} effective active)")
        print(f"  Frontend: {len(gta_frontend)} GTA + {len(by_request_frontend)} by-request")

        sections = {
            "headline_counts": gen_headline_counts(
                all_scraper, gta_frontend, by_request_frontend, alerting_platforms
            ),
            "last_updated":       gen_last_updated(api_sha, scraper_sha, frontend_sha),
            "course_counts":      gen_course_counts(all_scraper),
            "courses_by_platform": gen_courses_by_platform(all_scraper),
            "coverage_gaps":      gen_coverage_gaps(all_scraper, gta_frontend, by_request_frontend),
            "cross_platform_duplicates": gen_cross_platform_duplicates(all_scraper),
            "platforms_status":   gen_platforms_status(alerting_platforms),
        }

        if args.dry_run:
            print("\n--dry-run: skipping STATE.md write.")
            return

        if STATE_MD.exists():
            existing = STATE_MD.read_text()
            new_content = rewrite_autogen(existing, sections)
        else:
            raise RuntimeError("docs/STATE.md not found — scaffold must exist before running.")

        if existing == new_content:
            print("\ndocs/STATE.md is already up to date — no write needed.")
        else:
            STATE_MD.write_text(new_content)
            print(f"\nWrote {STATE_MD}")

        emit_courses_json(all_scraper, api_sha, scraper_sha, frontend_sha)

        print(f"\nScraper SHA:  {scraper_sha}")
        print(f"Frontend SHA: {frontend_sha}")
        print(f"API SHA:      {api_sha}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
