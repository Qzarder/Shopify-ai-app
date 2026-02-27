from pathlib import Path
from fastapi import APIRouter, HTTPException

from app.services.csv_validation import validate_shopify_csv
from app.services.csv_parser import parse_orders_csv
from app.services.csv_filter import filter_orders
from app.services.csv_aggregate import aggregate_orders
from app.services.csv_export import export_csv
from app.services.csv_processor import process_csv
from app.services.payment_store import is_paid

if output_csv.exists():
    raise HTTPException(
        status_code=409,
        detail="File already processed"
    )


router = APIRouter()

UPLOADS_DIR = Path("tmp")
PROCESSED_DIR = Path("data/processed")

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/process/{file_id}")
def process_file(file_id: str):
    if not is_paid(file_id):
        raise HTTPException(status_code=402, detail="Not paid")

    input_csv = UPLOADS_DIR / f"{file_id}.csv"
    if not input_csv.exists():
        raise HTTPException(status_code=404, detail="Input file not found")

    output_csv = PROCESSED_DIR / f"{file_id}_shopify.csv"

    process_csv(input_csv, output_csv)

    return {
        "status": "done",
        "download_url": f"/download/{file_id}"
    }
