
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
PAYMENTS_DIR = BASE_DIR / "tmp" / "payments"
PAYMENTS_DIR.mkdir(parents=True, exist_ok=True)

def mark_paid(file_id: str):
    path = PAYMENTS_DIR / f"{file_id}.json"
    path.write_text(json.dumps({"paid": True}))
    print("PAYMENTS_DIR:", PAYMENTS_DIR.resolve())

def is_paid(file_id: str) -> bool:
#    path = PAYMENTS_DIR / f"{file_id}.json"
 #   if not path.exists():
  #      return False
  #  data = json.loads(path.read_text())
  #  return data.get("paid") is True
    return True