import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from app.config import settings
from app.database import supabase_admin
from app.dependencies import get_current_user
from app.email import send_paid_signup_email
from app.schemas import CheckoutSessionRequest
from datetime import datetime, timezone

stripe.api_key = settings.stripe_secret_key

router = APIRouter(tags=["billing"])


@router.post("/create-checkout-session")
def create_checkout_session(body: CheckoutSessionRequest, current_user=Depends(get_current_user)):
    profile_result = supabase_admin.table("user_profiles").select("stripe_customer_id").eq("id", str(current_user.id)).maybe_single().execute()
    profile = profile_result.data or {}

    customer_id = profile.get("stripe_customer_id")
    email = body.email or current_user.email

    if not customer_id:
        customer = stripe.Customer.create(
            email=email,
            metadata={"supabase_user_id": str(current_user.id)},
        )
        customer_id = customer.id
        supabase_admin.table("user_profiles").update({"stripe_customer_id": customer_id}).eq("id", str(current_user.id)).execute()

    session_params = {
        "customer": customer_id,
        "payment_method_types": ["card"],
        "line_items": [{"price": settings.stripe_price_id, "quantity": 1}],
        "mode": "subscription",
        "success_url": settings.success_url + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": settings.cancel_url,
        "metadata": {"supabase_user_id": str(current_user.id)},
    }
    if settings.founder_coupon_id:
        session_params["discounts"] = [{"coupon": settings.founder_coupon_id}]

    try:
        session = stripe.checkout.Session.create(**session_params)
    except stripe.StripeError as e:
        if settings.founder_coupon_id:
            # Coupon rejected — retry at full price so checkout never blocks
            session_params.pop("discounts", None)
            try:
                session = stripe.checkout.Session.create(**session_params)
            except stripe.StripeError as e2:
                raise HTTPException(status_code=400, detail=str(e2))
        else:
            raise HTTPException(status_code=400, detail=str(e))

    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/subscription/cancel")
def cancel_subscription(current_user=Depends(get_current_user)):
    result = supabase_admin.table("user_profiles").select("stripe_subscription_id").eq("id", str(current_user.id)).maybe_single().execute()
    profile = result.data or {}
    subscription_id = profile.get("stripe_subscription_id")

    if not subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")

    try:
        stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True, "message": "Subscription will cancel at end of billing period"}


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except stripe.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        _handle_subscription_deleted(event["data"]["object"])

    return {"received": True}


def _handle_checkout_completed(session: dict):
    user_id = session.get("metadata", {}).get("supabase_user_id")
    if not user_id:
        return

    subscription_id = session.get("subscription")
    customer_id = session.get("customer")

    trial_end = None
    if subscription_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            if sub.get("trial_end"):
                trial_end = datetime.fromtimestamp(sub["trial_end"], tz=timezone.utc).isoformat()
        except Exception:
            pass

    updates = {
        "is_active": True,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
    }
    if trial_end:
        updates["trial_end"] = trial_end

    supabase_admin.table("user_profiles").update(updates).eq("id", user_id).execute()

    profile_result = supabase_admin.table("user_profiles").select("email").eq("id", user_id).maybe_single().execute()
    user_email = (profile_result.data or {}).get("email") or ""
    send_paid_signup_email(
        user_email=user_email,
        stripe_subscription_id=subscription_id or "",
        amount_cad=9.99,
    )


def _handle_subscription_deleted(subscription: dict):
    subscription_id = subscription.get("id")
    if not subscription_id:
        return

    result = supabase_admin.table("user_profiles").select("id").eq("stripe_subscription_id", subscription_id).maybe_single().execute()
    if not result.data:
        return

    user_id = result.data["id"]

    supabase_admin.table("user_profiles").update({
        "is_active": False,
        "stripe_subscription_id": None,
        "trial_end": None,
    }).eq("id", user_id).execute()

    supabase_admin.table("alert_profiles").update({"active": False}).eq("user_id", user_id).execute()
