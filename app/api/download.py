from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse


router = APIRouter()

PROCESSED_DIR = Path("data/processed")


@router.get("/download/{file_id}")
def download_file(file_id: str):
    path = PROCESSED_DIR / f"{file_id}_shopify.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="text/csv",
        filename="shopify_import.csv"
    )

