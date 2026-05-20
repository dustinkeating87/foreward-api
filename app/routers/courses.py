import json
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)

router = APIRouter()

_COURSES_FILE = Path(__file__).parent.parent.parent / "docs" / "courses.json"

try:
    _courses_data = json.loads(_COURSES_FILE.read_text())
    log.info("courses.json loaded: %d courses", len(_courses_data.get("courses", [])))
except Exception as exc:
    log.error("courses.json failed to load from %s: %s", _COURSES_FILE, exc)
    _courses_data = None


@router.get("/courses")
def get_courses():
    if _courses_data is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": "courses.json not generated yet",
                "detail": "Run scripts/refresh_state.py to generate",
            },
        )
    return JSONResponse(
        content=_courses_data,
        headers={"Cache-Control": "public, max-age=300"},
    )
