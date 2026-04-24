from fastapi import APIRouter, HTTPException, Depends
from app.database import supabase_admin
from app.dependencies import get_current_user
from datetime import datetime, timezone

router = APIRouter(tags=["invites"])


@router.post("/redeem-invite")
def redeem_invite(body: dict, current_user=Depends(get_current_user)):
    code = body.get("code", "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="Invite code is required")

    result = supabase_admin.table("invite_codes").select("*").eq("code", code).maybe_single().execute()
    invite = result.data

    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite code")

    if invite.get("used"):
        raise HTTPException(status_code=409, detail="This invite code has already been used")

    supabase_admin.table("invite_codes").update({
        "used": True,
        "used_by": str(current_user.id),
        "used_at": datetime.now(timezone.utc).isoformat()
    }).eq("code", code).execute()

    supabase_admin.table("user_profiles").update({
        "is_beta": True
    }).eq("id", str(current_user.id)).execute()

    return {"ok": True, "message": "Invite code redeemed successfully"}
