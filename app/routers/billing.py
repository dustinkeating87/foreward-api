import stripe
from fastapi import APIRouter, HTTPException, Request, Depends
from app.config import settings
from app.database import supabase_admin
from app.dependencies import get_current_user
from app.schemas import CheckoutSessionRequest

stripe.api_key = settings.stripe_secret_key

router = APIRouter(tags=["billing"])


@router.post("/create-checkout-session")
def create_checkout_session(body: CheckoutSessionRequest, current_user=Depends(get_current_user)):
    profile_result = supabase_admin.table("user_profiles").select("stripe_customer_id").eq("id", str(current_user.id)).maybe_single().execute()
    profile = profile_result.data or {}

    customer_id = profile.get("stripe_customer_id")
    email = body.email or current_user.email

    # Reuse existing Stripe customer or create a new one
    if not customer_id:
        customer = stripe.Customer.create(
            email=email,
            metadata={"supabase_user_id": str(current_user.id)},
        )
        customer_id = customer.id
        supabase_admin.table("user_profiles").update({"stripe_customer_id": customer_id}).eq("id", str(current_user.id)).execute()

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=settings.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.cancel_url,
            metadata={"supabase_user_id": str(current_user.id)},
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"checkout_url": session.url, "session_id": session.id}


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

    supabase_admin.table("user_profiles").update({
        "is_active": True,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
    }).eq("id", user_id).execute()


def _handle_subscription_deleted(subscription: dict):
    subscription_id = subscription.get("id")
    if not subscription_id:
        return

    # Find affected user before clearing the subscription ID
    result = supabase_admin.table("user_profiles").select("id").eq("stripe_subscription_id", subscription_id).maybe_single().execute()
    if not result.data:
        return

    user_id = result.data["id"]

    supabase_admin.table("user_profiles").update({
        "is_active": False,
        "stripe_subscription_id": None,
    }).eq("id", user_id).execute()

    supabase_admin.table("alert_profiles").update({"active": False}).eq("user_id", user_id).execute()
