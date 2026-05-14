import json
import os

# In-memory store (fast path)
processing_status: dict = {}

_STATUS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "status")
os.makedirs(_STATUS_DIR, exist_ok=True)

def _status_path(file_id: str) -> str:
    return os.path.join(_STATUS_DIR, f"{file_id}.json")


def set_status(file_id: str, data: dict):
    """Write status to memory and disk (only for terminal/important states)."""
    processing_status[file_id] = data
    # Persist completed/error states so they survive restart
    if data.get("status") in ("completed", "error"):
        try:
            with open(_status_path(file_id), "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass


def get_status(file_id: str) -> dict | None:
    if file_id in processing_status:
        return processing_status[file_id]
    # Fallback: check disk for completed/error states persisted before restart
    path = _status_path(file_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            processing_status[file_id] = data
            return data
        except (OSError, json.JSONDecodeError):
            pass
    return None
