import os
import stripe
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


# Загружаем переменные окружения в первую очередь
load_dotenv()

# Инициализируем ключи Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Импорт роутеров и сервисов
from app.api import checkout, process, health, upload, products, preview
from app.api.status import router as status_router
from app.services.payment_store import mark_paid
from app.services.limits import check_and_update_limit
from fastapi.responses import JSONResponse # Добавь JSONResponse, если его нет

# ---------- PATHS ----------
BASE_DIR = Path(__file__).resolve().parent  # папка app/
STATIC_DIR = BASE_DIR / "static"

# ---------- APP SETUP ----------
app = FastAPI(title="Shopify AI Importer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://admin.shopify.com", "https://csv-magic-cleaner-blue-lake-2582.fly.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- STATIC FILES ----------
if not STATIC_DIR.exists():
    raise RuntimeError(f"Static directory not found: {STATIC_DIR}")

# Подключаем папку со статикой
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------- HTML PAGES ----------
@app.get("/", response_class=FileResponse)
def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Index file not found")
    return FileResponse(index_file)

@app.get("/success", response_class=FileResponse)
def success():
    # Используем безопасный путь Path вместо хардкода строки
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Index file not found")
    return FileResponse(index_file)

# ---------- WEBHOOK ----------
@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not WEBHOOK_SECRET:
        print("CRITICAL: STRIPE_WEBHOOK_SECRET is not set in environment.")
        raise HTTPException(status_code=500, detail="Webhook secret missing")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            WEBHOOK_SECRET
        )
    except ValueError as e:
        # Неверный формат payload
        print("WEBHOOK ERROR (ValueError):", e)
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Неверная подпись (кто-то пытается подделать запрос от Stripe)
        print("WEBHOOK ERROR (SignatureVerificationError):", e)
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print("WEBHOOK ERROR (Unknown):", e)
        raise HTTPException(status_code=400, detail="Webhook processing failed")

    # Обрабатываем успешную оплату
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        
        # Безопасно достаем file_id из метадаты или client_reference_id
        metadata = session.get("metadata") or {}
        file_id = metadata.get("file_id") or session.get("client_reference_id")
        
        if file_id:
            mark_paid(file_id)
            print(f"✅ MARKED PAID: {file_id}")
        else:
            print("⚠️ WEBHOOK WARNING: file_id not found in session")

    return {"status": "ok"}



# ---------- ROUTERS ----------
# Подключаем все остальные эндпоинты
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(checkout.router)
app.include_router(process.router)
app.include_router(status_router)
app.include_router(products.router)
app.include_router(preview.router)