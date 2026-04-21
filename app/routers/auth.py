from fastapi import APIRouter, HTTPException, Depends
from app.schemas import SignupRequest, LoginRequest
from app.database import supabase, supabase_admin
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201)
def signup(body: SignupRequest):
    try:
        response = supabase.auth.sign_up({"email": body.email, "password": body.password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not response.user:
        raise HTTPException(status_code=400, detail="Signup failed")

    # user_profiles row is created by the Supabase trigger on auth.users insert
    return {
        "user_id": str(response.user.id),
        "email": response.user.email,
        "message": "Signup successful. Check your email to confirm your account.",
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
    }
