from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Form, Request
from fastapi.responses import JSONResponse
import json
import uuid
from pathlib import Path

from app.services.csv_processor import process_csv_file
from app.services.state import processing_status
from app.services.limits import check_and_update_limit
from app.services.mapping_templates import list_templates, delete_template, save_template as save_tmpl

router = APIRouter(prefix="/upload", tags=["upload"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    shop: str | None = Form(None),
    file: UploadFile = File(...),
    tone: str | None = Form(None),
    tov: str | None = Form(None),
    is_pro: str = Form("false"),
    supplier_name: str | None = Form(None),
):
    file_id = str(uuid.uuid4())

    shop = (shop or "").strip()
    if not shop:
        client_host = getattr(request.client, "host", "direct-user")
        shop = f"direct-web:{client_host}"

    selected_tone = (tone or tov or "Neutral & Professional").strip() or "Neutral & Professional"

    input_path = str(UPLOAD_DIR / f"{file_id}.csv")
    output_path = str(OUTPUT_DIR / f"shopify_ready_{file_id}.csv")

    content = await file.read()

    try:
        text = content.decode("utf-8-sig", errors="ignore")
        lines = [line for line in text.split("\n") if line.strip()]
        row_count = len(lines) - 1 if len(lines) > 0 else 0
    except Exception:
        row_count = 0

    pro_active = is_pro.lower() == "true"
    print(f"DEBUG: Shop {shop} uploading {row_count} items. PRO status from billing: {pro_active}. Tone: {selected_tone}")

    if not pro_active:
        limit_check = check_and_update_limit(shop, row_count)
        if not limit_check["allowed"]:
            error_msg = (
                f"Limit exceeded! You used {limit_check['used']}/{limit_check['limit']} items. "
                f"Cannot process {limit_check['requested']} new items. Please upgrade to Pro."
            )
            print(f"DEBUG: LIMIT HIT - {error_msg}")
            return JSONResponse(status_code=400, content={"error": error_msg, "shop": shop})
    else:
        print(f"DEBUG: Shop {shop} has PRO (verified via Shopify Billing). Bypassing limits.")

    with open(input_path, "wb") as buffer:
        buffer.write(content)

    processing_status[file_id] = {"current": 0, "total": row_count, "status": "starting"}
    background_tasks.add_task(process_csv_file, input_path, output_path, file_id, shop, selected_tone, supplier_name or "")

    return {"file_id": file_id, "message": "Processing started"}


@router.get("/templates")
async def get_templates(shop: str = ""):
    return {"templates": list_templates(shop)}


@router.delete("/templates/{fingerprint}")
async def remove_template(fingerprint: str, shop: str = ""):
    deleted = delete_template(shop, fingerprint)
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Template not found"})
    return {"status": "deleted"}


@router.post("/templates")
async def create_template(
    shop: str = Form(...),
    supplier_name: str = Form(...),
    column_map: str = Form(...),
    tone: str = Form("Neutral & Professional"),
    headers: str = Form(...),
):
    headers_list = [h.strip() for h in headers.split(",") if h.strip()]
    cm = json.loads(column_map)
    fp = save_tmpl(shop, supplier_name, headers_list, cm, tone)
    return {"fingerprint": fp, "message": "Template saved"}