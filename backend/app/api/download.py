from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

# Пока закомментируем проверку оплаты, чтобы не было ошибок импорта, если файла нет
# from app.services.payment_store import is_paid

router = APIRouter()

# --- АБСОЛЮТНЫЕ ПУТИ (Точно такие же как в upload.py) ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

@router.get("/download/{file_id}")
def download_file(file_id: str):
    # ИСПРАВЛЕНО: Имя файла строго совпадает с тем, что генерирует процессор
    path = OUTPUT_DIR / f"shopify_ready_{file_id}.csv"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found or still processing")

    # Отдаем файл клиенту
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename="shopify_ready_import.csv" # Красивое имя файла, которое увидит юзер при скачивании
    )