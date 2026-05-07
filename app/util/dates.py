import re
from datetime import datetime


def _parse_iso(ts: str) -> datetime:
    # Python 3.9 fromisoformat rejects fractional seconds unless exactly 0, 3, or 6 digits.
    # Supabase/PostgREST returns any precision. Normalize to 6 digits before parsing.
    ts = ts.replace("Z", "+00:00")
    ts = re.sub(r"\.(\d+)(?=[+-])", lambda m: "." + m.group(1).ljust(6, "0")[:6], ts)
    return datetime.fromisoformat(ts)
