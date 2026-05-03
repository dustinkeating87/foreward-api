from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.database import supabase_admin

router = APIRouter(tags=["activity"])


@router.get("/activity")
def get_activity():
    result = (
        supabase_admin.table("sent_slots")
        .select("course_name, tee_time, players, created_at, taken_at")
        .filter("course_name", "not.is", "null")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    response = JSONResponse(content=result.data or [])
    response.headers["Cache-Control"] = "public, max-age=30"
    return response
