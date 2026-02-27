from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/success")
def success():
    return {"status": "payment_success"}

@router.get("/cancel")
def cancel():
    return {"status": "payment_cancelled"}
