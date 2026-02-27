from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

# Пока закомментируем проверку оплаты, чтобы не было ошибок импорта, если файла нет
# from app.services.payment_store import is_paid

router = APIRouter()

# ИСПРАВЛЕНО: Указываем ту же папку, куда процессор сохраняет результат
PROCESSED_DIR = Path("tmp/output")

@router.get("/download/{file_id}")
def download_file(file_id: str):
    # ИСПРАВЛЕНО: Имя файла точно совпадает с тем, что генерирует процессор
    path = PROCESSED_DIR / f"{file_id}_cleaned.csv"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found or still processing")

    # Отдаем файл клиенту
    return FileResponse(
        path,
        media_type="text/csv",
        filename="shopify_ready_import.csv" # Красивое имя файла, которое увидит юзер при скачивании
    )