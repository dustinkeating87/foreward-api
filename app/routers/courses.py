from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.util.courses import all_courses

router = APIRouter()


@router.get("/courses")
def get_courses():
    courses = [
        {"key": c["key"], "name": c["display_name"], "platform": c["platform"]}
        for c in all_courses()
    ]
    return JSONResponse(
        content={"courses": courses},
        headers={"Cache-Control": "public, max-age=300"},
    )
