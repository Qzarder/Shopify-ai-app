from dotenv import load_dotenv
import os

load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL")

if not STRIPE_SECRET_KEY:
    raise RuntimeError("STRIPE_SECRET_KEY is not set")

if not STRIPE_SUCCESS_URL:
    raise RuntimeError("STRIPE_SUCCESS_URL is not set")

if not STRIPE_CANCEL_URL:
    raise RuntimeError("STRIPE_CANCEL_URL is not set")
