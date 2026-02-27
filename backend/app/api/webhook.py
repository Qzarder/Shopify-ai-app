import os
import json
import stripe
from fastapi import APIRouter, Request, HTTPException
from app.config import STRIPE_SECRET_KEY
from app.services.payment_store import mark_paid

router = APIRouter()

stripe.api_key = STRIPE_SECRET_KEY
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@router.post("/webhook/stripe ")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            WEBHOOK_SECRET
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook")

    event_type = event["type"]
    session = event["data"]["object"]
    print("SESSION RAW:", json.dumps(session, indent=2))

    # 1️⃣ УСПЕШНАЯ ОПЛАТА ЧЕРЕЗ CHECKOUT
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        print("METADATA:", session.get("metadata"))
        metadata = session.get("metadata") or {}
        file_id = (metadata.get("file_id")
        or session.get("client_reference_id"))
        print("FILE_ID:", file_id)
     
        if not file_id:
            raise ValueError("file_id not found in session")
        if file_id:
            mark_paid(file_id)
            print("MARKED PAID:", file_id)
        

    # 2️⃣ (на будущее) УСПЕШНЫЙ PAYMENT INTENT
    elif event_type == "payment_intent.succeeded":
        pass

    # 3️⃣ (на будущее) ОШИБКА ОПЛАТЫ
    elif event_type == "checkout.session.async_payment_failed":
        pass

    return {"status": "ok"}
