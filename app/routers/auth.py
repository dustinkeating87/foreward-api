from fastapi import APIRouter, HTTPException, Depends
from app.schemas import SignupRequest, LoginRequest
from app.database import supabase, supabase_admin
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201)
def signup(body: SignupRequest):
    try:
        response = supabase_admin.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not response.user:
        raise HTTPException(status_code=400, detail="Signup failed")

    try:
        session_response = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "access_token": session_response.session.access_token,
        "refresh_token": session_response.session.refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(response.user.id),
            "email": response.user.email,
        },
    }


@router.post("/login")
def login(body: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password({"email": body.email, "password": body.password})
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not response.user or not response.session:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(response.user.id),
            "email": response.user.email,
        },
    }


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    result = supabase_admin.table("user_profiles").select("*").eq("id", str(current_user.id)).maybe_single().execute()
    profile = result.data or {}
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "is_active": profile.get("is_active", False),
        "is_beta": profile.get("is_beta", False),
        "stripe_customer_id": profile.get("stripe_customer_id"),
        "notify_email": profile.get("notify_email"),
        "notify_phone": profile.get("notify_phone"),
    }


@router.patch("/me")
def update_me(body: dict, current_user=Depends(get_current_user)):
    allowed = {"notify_email", "notify_phone"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    supabase_admin.table("user_profiles").update(updates).eq("id", str(current_user.id)).execute()
    return {"ok": True}
