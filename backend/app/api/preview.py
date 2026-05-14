from fastapi import APIRouter
from fastapi.responses import JSONResponse
import csv
from pathlib import Path

router = APIRouter(prefix="/preview", tags=["preview"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"


@router.get("/{file_id}")
async def preview(file_id: str, limit: int = 5):
    in_path = UPLOAD_DIR / f"{file_id}.csv"
    out_path = OUTPUT_DIR / f"shopify_ready_{file_id}.csv"

    if not out_path.exists():
        return JSONResponse(status_code=404, content={"error": "Processed file not found"})

    has_original = in_path.exists()
    original_rows = {}
    if has_original:
        with open(in_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                original_rows[i] = dict(row)

    results = []
    with open(out_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            orig = original_rows.get(i, {})
            item = {
                "title": row.get("Title", ""),
                "body_html": row.get("Body (HTML)", ""),
                "handle": row.get("Handle", ""),
                "vendor": row.get("Vendor", ""),
                "product_type": row.get("Type", ""),
                "tags": row.get("Tags", ""),
                "price": row.get("Variant Price", ""),
                "sku": row.get("Variant SKU", ""),
                "image_src": row.get("Image Src", ""),
            }
            if has_original and orig:
                orig_title_col = next((k for k in orig if "title" in k.lower() or "name" in k.lower()), None)
                orig_desc_col = next((k for k in orig if "desc" in k.lower() or "body" in k.lower()), None)
                item["original"] = {
                    "title": orig.get(orig_title_col, "") if orig_title_col else orig.get(next(iter(orig), ""), ""),
                    "description": orig.get(orig_desc_col, "") if orig_desc_col else "",
                    "source_row": {k: str(v)[:100] for k, v in list(orig.items())[:5]}
                }
            results.append(item)

    return {"rows": results, "total": len(results)}
