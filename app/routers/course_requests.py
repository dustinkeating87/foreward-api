"""
course_requests.py — Course request endpoint

Accepts public submissions of course requests from the Good Lie frontend.
Stores in Supabase course_requests table and sends an email notification
to hello@goodlie.golf so we know what courses users want added.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.database import supabase_admin
import logging
import os
import httpx

log = logging.getLogger("goodlie-api")
router = APIRouter()


class CourseRequestIn(BaseModel):
    course_name: str
    email: str = ""


@router.post("/api/course-requests", status_code=200)
async def submit_course_request(body: CourseRequestIn):
    course = body.course_name.strip()
    email  = body.email.strip()

    if not course:
        return {"ok": False, "error": "course_name is required"}

    # Store in Supabase
    try:
        supabase_admin.table("course_requests").insert({
            "course_name": course,
            "email":       email or None,
        }).execute()
    except Exception as e:
        log.warning("course_requests insert failed: %s", e)
        # Don't fail the request — the notification below is enough

    # Notify via SendGrid
    try:
        sg_key = os.environ.get("SENDGRID_API_KEY", "")
        if sg_key:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {sg_key}", "Content-Type": "application/json"},
                    json={
                        "personalizations": [{"to": [{"email": "hello@goodlie.golf"}]}],
                        "from":    {"email": "hello@goodlie.golf", "name": "Good Lie"},
                        "subject": f"Course Request: {course}",
                        "content": [{"type": "text/plain", "value": f"Course: {course}\nEmail: {email or 'not provided'}"}],
                    }
                )
    except Exception as e:
        log.warning("course_request notification email failed: %s", e)

    log.info("Course request received: %s (from %s)", course, email or "anonymous")
    return {"ok": True}
