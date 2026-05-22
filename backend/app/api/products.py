from fastapi import APIRouter
from fastapi.responses import JSONResponse
import csv
from pathlib import Path
from app.services.state import get_status

router = APIRouter(prefix="/products", tags=["products"])

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs"


@router.get("/{file_id}")
async def get_products(file_id: str):
    # Сначала пробуем читать из файла
    file_path = OUTPUT_DIR / f"shopify_ready_{file_id}.csv"
    if file_path.exists():
        products = []
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get("Title", "").strip()
                if not title:
                    continue
                product = {
                    "title": title,
                    "descriptionHtml": row.get("Body (HTML)", ""),
                    "vendor": row.get("Vendor", ""),
                    "productType": row.get("Type", ""),
                    "tags": [t.strip() for t in row.get("Tags", "").split(",") if t.strip()],
                    "variants": [{"price": row.get("Variant Price", "0.00"), "sku": row.get("Variant SKU", "")}],
                }
                if row.get("Image Src"):
                    product["images"] = [{"src": row.get("Image Src")}]
                products.append(product)
        return {"status": "completed", "products": products, "count": len(products)}

    # Файл не найден — пробуем взять из персистентного статуса на диске
    status = get_status(file_id)
    if status and status.get("products"):
        products = status["products"]
        return {"status": "completed", "products": products, "count": len(products)}

    return JSONResponse(status_code=404, content={"error": "Products not found. Please reprocess your file."})
