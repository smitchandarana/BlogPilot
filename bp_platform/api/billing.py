"""Stripe billing — checkout, webhooks, subscription management."""

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request

from bp_platform.config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, APP_BASE_URL
from bp_platform.api.auth import get_current_user
from bp_platform.models.database import User, BillingEvent, get_db

router = APIRouter(prefix="/platform/billing", tags=["billing"])

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


@router.post("/create-checkout")
async def create_checkout(user: dict = Depends(get_current_user)):
    """Create a Stripe Checkout session for subscription."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    user_id = user["sub"]
    with get_db() as db:
        u = db.query(User).filter_by(id=user_id).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")

        # Create or get Stripe customer
        if not u.stripe_customer_id:
            customer = stripe.Customer.create(email=u.email, metadata={"user_id": user_id})
            u.stripe_customer_id = customer.id
            db.commit()

    session = stripe.checkout.Session.create(
        customer=u.stripe_customer_id,
        mode="subscription",
        line_items=[{
            "price": "price_REPLACE_WITH_YOUR_PRICE_ID",  # Set your Stripe price ID
            "quantity": 1,
        }],
        success_url=f"{APP_BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_BASE_URL}/billing/cancel",
        metadata={"user_id": user_id},
    )

    return {"checkout_url": session.url}


@router.post("/webhook")
async def webhook(request: Request):
    """Handle Stripe webhook events."""
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(body, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    # Log event
    with get_db() as db:
        db.add(BillingEvent(
            stripe_event_id=event["id"],
            event_type=event_type,
            payload=data,
            user_id=data.get("metadata", {}).get("user_id"),
        ))
        db.commit()

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        sub_id = data.get("subscription")
        if user_id:
            with get_db() as db:
                u = db.query(User).filter_by(id=user_id).first()
                if u:
                    u.subscription_status = "active"
                    u.stripe_subscription_id = sub_id
                    db.commit()

    elif event_type == "customer.subscription.deleted":
        sub_id = data.get("id")
        with get_db() as db:
            u = db.query(User).filter_by(stripe_subscription_id=sub_id).first()
            if u:
                u.subscription_status = "cancelled"
                db.commit()

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        with get_db() as db:
            u = db.query(User).filter_by(stripe_customer_id=customer_id).first()
            if u:
                u.subscription_status = "past_due"
                db.commit()

    return {"received": True}


@router.get("/subscription")
async def get_subscription(user: dict = Depends(get_current_user)):
    """Get current subscription status."""
    with get_db() as db:
        u = db.query(User).filter_by(id=user["sub"]).first()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")

        result = {
            "status": u.subscription_status,
            "stripe_customer_id": u.stripe_customer_id,
        }

        if u.stripe_subscription_id and STRIPE_SECRET_KEY:
            try:
                sub = stripe.Subscription.retrieve(u.stripe_subscription_id)
                result["current_period_end"] = sub.current_period_end
                result["cancel_at_period_end"] = sub.cancel_at_period_end
            except Exception:
                pass

        return result


@router.post("/cancel")
async def cancel_subscription(user: dict = Depends(get_current_user)):
    """Cancel subscription at end of current period."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured")

    with get_db() as db:
        u = db.query(User).filter_by(id=user["sub"]).first()
        if not u or not u.stripe_subscription_id:
            raise HTTPException(status_code=404, detail="No active subscription")

    stripe.Subscription.modify(
        u.stripe_subscription_id,
        cancel_at_period_end=True,
    )

    return {"status": "cancelling_at_period_end"}
