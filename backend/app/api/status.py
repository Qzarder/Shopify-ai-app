from fastapi import APIRouter
from app.services.state import processing_status

router = APIRouter()

@router.get("/status/{file_id}")
def get_status(file_id: str):
    status_data = processing_status.get(file_id)
    
    if not status_data:
        return {"status": "not_found"}
        
    return status_data