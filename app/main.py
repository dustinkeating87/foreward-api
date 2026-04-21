from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, alerts, billing
from app.database import supabase, supabase_admin
from app.config import settings

app = FastAPI(title="Tee Sniper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(billing.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/export-alerts")
def export_alerts(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    """
    Returns all active alert profiles in alerts.json format for the polling engine.
    Accepts either a Supabase Bearer JWT or an X-Api-Key header.
    """
    if x_api_key:
        if not settings.export_api_key or x_api_key != settings.export_api_key:
            raise HTTPException(status_code=403, detail="Invalid API key")
    elif authorization:
        token = authorization.removeprefix("Bearer ").strip()
        try:
            response = supabase.auth.get_user(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = supabase_admin.table("alert_profiles").select("*").eq("active", True).execute()

    export = []
    for row in result.data or []:
        export.append({
            "id": row["id"],
            "email": row.get("notify_email") or "",
            "phone": row.get("notify_phone") or "",
            "courses": row.get("courses") or [],
            "date_from": row["date_from"],
            "date_to": row["date_to"],
            "time_from": row["time_from"],
            "time_to": row["time_to"],
            "players": row["players"],
            "holes": row["holes"],
        })

    return export
