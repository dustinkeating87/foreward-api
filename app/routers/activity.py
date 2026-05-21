from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.database import supabase_admin

router = APIRouter(tags=["activity"])


@router.get("/activity")
def get_activity(limit: int = Query(default=50, ge=1, le=100)):
    result = (
        supabase_admin.table("sent_slots")
        .select("course_name, tee_time, players")
        .filter("course_name", "not.is", "null")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    response = JSONResponse(content=result.data or [])
    response.headers["Cache-Control"] = "public, max-age=300"
    return response
