from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
import uuid
import os
from app.services.csv_processor import process_csv_file
from app.services.state import processing_status
from app.services.limits import check_and_update_limit 

router = APIRouter(prefix="/upload", tags=["upload"]) 

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@router.post("/")
async def upload_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    tov: str = Form("auto")
):
    merchant_id = "merchant_test_001" 

    file_id = str(uuid.uuid4())
    input_path = f"{UPLOAD_DIR}/{file_id}.csv"
    output_path = f"{OUTPUT_DIR}/shopify_ready_{file_id}.csv"
    
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
        
    print(f"DEBUG: Merchant {merchant_id} uploading {row_count} items.")
        
    # 3. ПРОВЕРЯЕМ ЛИМИТЫ ДО СОХРАНЕНИЯ
    limit_check = check_and_update_limit(merchant_id, row_count)
    if not limit_check["allowed"]:
        error_msg = f"Limit exceeded! You used {limit_check['used']}/{limit_check['limit']} items. Cannot process {limit_check['requested']} new items. Please upgrade to Pro."
        print(f"DEBUG: LIMIT HIT - {error_msg}")
        return JSONResponse(status_code=400, content={"error": error_msg})
        
    # 4. Если лимит прошел — сохраняем файл на жесткий диск
    with open(input_path, "wb") as buffer:
        buffer.write(content)
        
    # 5. Запускаем ИИ
    processing_status[file_id] = {"current": 0, "total": row_count, "status": "starting"}
    background_tasks.add_task(process_csv_file, input_path, output_path, file_id, tov)
    
    return {"file_id": file_id, "message": "Processing started"}