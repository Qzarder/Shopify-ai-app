"""
Shopify session-token (App Bridge JWT) verification.

The embedded frontend obtains a session token via App Bridge `shopify.idToken()`
and sends it as `Authorization: Bearer <token>` on every request to this backend.
We verify the HS256 signature with the app's API secret and derive the shop
domain from the verified `dest` claim — so the client can no longer spoof which
shop it is, nor the Pro status tied to that shop.

Docs: https://shopify.dev/docs/apps/auth/session-tokens
"""
import os

import jwt
from fastapi import Header, HTTPException

API_KEY = os.getenv("SHOPIFY_API_KEY", "")
API_SECRET = os.getenv("SHOPIFY_API_SECRET", "")
# Shared secret for trusted server-to-server calls from the Fly app server
# (the /products endpoint is fetched by the app's `action`, not the browser).
BACKEND_SHARED_SECRET = os.getenv("BACKEND_SHARED_SECRET", "")

if not API_SECRET:
    print("[AUTH] WARNING: SHOPIFY_API_SECRET is not set — session tokens cannot be verified!")
if not API_KEY:
    print("[AUTH] WARNING: SHOPIFY_API_KEY is not set — session token audience cannot be checked!")


def _shop_from_dest(dest: str) -> str:
    # dest looks like "https://my-store.myshopify.com"
    return dest.replace("https://", "").replace("http://", "").strip("/")


def verify_session_token(authorization: str | None = Header(None)) -> str:
    """
    FastAPI dependency. Returns the verified shop domain (e.g. "store.myshopify.com").
    Raises 401 if the token is missing or invalid.
    """
    if not API_SECRET:
        # Misconfiguration on the server — fail loudly rather than silently trusting.
        raise HTTPException(status_code=500, detail="Server auth not configured (SHOPIFY_API_SECRET missing)")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing session token")

    token = authorization.split(" ", 1)[1].strip()

    try:
        decode_kwargs = {
            "algorithms": ["HS256"],
            "options": {"require": ["exp", "dest"]},
        }
        if API_KEY:
            decode_kwargs["audience"] = API_KEY
        else:
            decode_kwargs["options"]["verify_aud"] = False

        payload = jwt.decode(token, API_SECRET, **decode_kwargs)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session token: {e}")

    dest = payload.get("dest", "")
    shop = _shop_from_dest(dest)
    if not shop.endswith(".myshopify.com"):
        raise HTTPException(status_code=401, detail="Invalid shop in session token")

    return shop


def verify_backend_secret(x_backend_secret: str | None = Header(None)) -> bool:
    """
    FastAPI dependency for trusted server-to-server calls (Fly app -> Render backend).
    If BACKEND_SHARED_SECRET is configured, the matching header is required.
    If it is not configured, the call is allowed (so the app keeps working until the
    secret is set on both servers).
    """
    if not BACKEND_SHARED_SECRET:
        print("[AUTH] WARNING: BACKEND_SHARED_SECRET not set — /products is unprotected.")
        return True
    if x_backend_secret != BACKEND_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid backend secret")
    return True
