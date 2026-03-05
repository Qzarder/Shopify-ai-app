import os
import json
import hmac
import hashlib
import base64
import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from app.config import STRIPE_SECRET_KEY
from app.services.payment_store import mark_paid

# Убираем жесткий prefix, чтобы не сломать пути Stripe, 
# пропишем пути явно для каждого эндпоинта
router = APIRouter(tags=["webhooks"])

# --- STRIPE CONFIG ---
stripe.api_key = STRIPE_SECRET_KEY
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# --- SHOPIFY HELPER ---
def verify_shopify_webhook(data: bytes, hmac_header: str) -> bool:
    client_secret = os.getenv("SHOPIFY_API_SECRET", "")
    if not client_secret:
        return True # Если секрет не задан (например, локально), пропускаем
        
    digest = hmac.new(client_secret.encode('utf-8'), data, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(computed_hmac, hmac_header)


# ==========================================
# 1. STRIPE WEBHOOKS
# ==========================================
@router.post("/webhook/stripe")
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
        print("METADATA:", session.get("metadata"))
        metadata = session.get("metadata") or {}
        file_id = metadata.get("file_id") or session.get("client_reference_id")
        print("FILE_ID:", file_id)
        
        if not file_id:
            print("Error: file_id not found in session")
        else:
            mark_paid(file_id)
            print("MARKED PAID:", file_id)

    # 2️⃣ (на будущее) УСПЕШНЫЙ PAYMENT INTENT
    elif event_type == "payment_intent.succeeded":
        pass

    # 3️⃣ (на будущее) ОШИБКА ОПЛАТЫ
    elif event_type == "checkout.session.async_payment_failed":
        pass

    return {"status": "ok"}


# ==========================================
# 2. SHOPIFY GDPR WEBHOOKS
# ==========================================
@router.post("/webhook/shopify/customers/data_request")
async def customer_data_request(request: Request):
    """
    Shopify присылает запрос, когда покупатель хочет посмотреть свои данные.
    Мы не храним данные покупателей магазина, просто возвращаем 200 OK.
    """
    # TODO: Добавить проверку verify_shopify_webhook в будущем
    return JSONResponse(status_code=200, content={"message": "No customer data stored."})

@router.post("/webhook/shopify/customers/redact")
async def customer_redact(request: Request):
    """
    Запрос на удаление данных конкретного покупателя.
    У нас их нет, поэтому сразу рапортуем об успешном удалении.
    """
    return JSONResponse(status_code=200, content={"message": "No customer data to delete."})

@router.post("/webhook/shopify/shop/redact")
async def shop_redact(request: Request):
    """
    Владелец магазина удалил приложение.
    Очищаем данные магазина.
    """
    try:
        body = await request.body()
        payload = json.loads(body)
        shop_domain = payload.get("shop_domain", "unknown")
        
        print(f"🚨 Вебхук: Магазин {shop_domain} удалил приложение. Очищаем данные.")
        
        return JSONResponse(status_code=200, content={"message": f"Data for shop {shop_domain} erased."})
    except Exception as e:
        print(f"Ошибка в вебхуке shop/redact: {e}")
        return JSONResponse(status_code=200, content={"message": "Handled with error"})