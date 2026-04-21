from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase, supabase_admin

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        response = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not response.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return response.user


def get_current_subscribed_user(user=Depends(get_current_user)):
    result = supabase_admin.table("user_profiles").select("*").eq("id", str(user.id)).maybe_single().execute()
    profile = result.data
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    if not profile.get("is_beta") and not profile.get("is_active"):
        raise HTTPException(status_code=403, detail="Active subscription required")
    return {"user": user, "profile": profile}
