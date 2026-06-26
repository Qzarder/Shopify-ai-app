from fastapi import APIRouter, Depends
from app.services.state import get_status
from app.services.shopify_auth import verify_session_token

router = APIRouter()


@router.get("/status/{file_id}")
def check_status(file_id: str, shop: str = Depends(verify_session_token)):
    data = get_status(file_id)
    if not data:
        return {"status": "not_found"}
    return data
