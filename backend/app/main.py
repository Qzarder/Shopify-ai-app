import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api import process, health, upload, products, preview
from app.api.status import router as status_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Shopify AI Importer")

_PROD_ORIGINS = [
    "https://admin.shopify.com",
    "https://csv-magic-cleaner-blue-lake-2582.fly.dev",
]
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
]
_is_dev = os.getenv("ENV", "production").lower() != "production"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_PROD_ORIGINS + (_DEV_ORIGINS if _is_dev else []),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(process.router)
app.include_router(status_router)
app.include_router(products.router)
app.include_router(preview.router)
