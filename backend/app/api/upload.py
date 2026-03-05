from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
import uuid
import os
from pathlib import Path
from app.services.csv_processor import process_csv_file
from app.services.state import processing_status
from app.services.limits import check_and_update_limit 

router = APIRouter(prefix="/upload", tags=["upload"]) 

# --- АБСОЛЮТНЫЕ ПУТИ ---
# Вычисляем точный путь до папки backend (на 3 уровня выше этого файла)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

# Железобетонно создаем папки
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/")
async def upload_file(
    background_tasks: BackgroundTasks, 
    merchant_id: str = Form(...),  
    file: UploadFile = File(...),
    tov: str = Form("auto"),       
    is_pro: str = Form("false")  # <-- ДОБАВЛЕН ПРИЕМ ФЛАГА ПОДПИСКИ ИЗ ФРОНТЕНДА
):
    file_id = str(uuid.uuid4())
    
    # Формируем строковые пути для процессора
    input_path = str(UPLOAD_DIR / f"{file_id}.csv")
    output_path = str(OUTPUT_DIR / f"shopify_ready_{file_id}.csv")
    
    # 1. Читаем файл в память ОДИН РАЗ
    content = await file.read()
    
    # 2. Считаем строки прямо из памяти (надежно на 100%)
    try:
        text = content.decode("utf-8-sig", errors="ignore")
        # Разбиваем на строки и убираем пустые
        lines = [line for line in text.split('\n') if line.strip()] 
        row_count = len(lines) - 1 if len(lines) > 0 else 0
    except Exception:
        row_count = 0
        
    pro_active = is_pro.lower() == "true"
    print(f"DEBUG: Merchant {merchant_id} uploading {row_count} items. PRO status: {pro_active}")
        
    # 3. ПРОВЕРЯЕМ ЛИМИТЫ ДО СОХРАНЕНИЯ (Только если нет PRO)
    if not pro_active:
        limit_check = check_and_update_limit(merchant_id, row_count)
        if not limit_check["allowed"]:
            error_msg = f"Limit exceeded! You used {limit_check['used']}/{limit_check['limit']} items. Cannot process {limit_check['requested']} new items. Please upgrade to Pro."
            print(f"DEBUG: LIMIT HIT - {error_msg}")
            # Добавил merchant_id в ответ, чтобы фронтенд знал, кого именно просить оплатить
            return JSONResponse(status_code=400, content={"error": error_msg, "merchant_id": merchant_id})
    else:
        print(f"DEBUG: Merchant {merchant_id} has PRO. Bypassing limits.")
        
    # 4. Если лимит прошел или есть PRO — сохраняем файл на жесткий диск
    with open(input_path, "wb") as buffer:
        buffer.write(content)
        
    # 5. Запускаем ИИ
    processing_status[file_id] = {"current": 0, "total": row_count, "status": "starting"}
    background_tasks.add_task(process_csv_file, input_path, output_path, file_id, merchant_id, tov)
    
    return {"file_id": file_id, "message": "Processing started"}