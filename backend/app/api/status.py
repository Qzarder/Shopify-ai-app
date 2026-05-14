from fastapi import APIRouter
from app.services.state import get_status

router = APIRouter()


@router.get("/status/{file_id}")
def check_status(file_id: str):
    data = get_status(file_id)
    if not data:
        return {"status": "not_found"}
    return data
