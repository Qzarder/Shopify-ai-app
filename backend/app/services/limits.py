import json
import os
from datetime import datetime

LIMITS_FILE = os.path.join(os.path.dirname(__file__), "user_limits.json")

FREE_TIER_LIMIT = 150


def _current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def load_limits() -> dict:
    if os.path.exists(LIMITS_FILE):
        with open(LIMITS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_limits(limits: dict):
    with open(LIMITS_FILE, "w", encoding="utf-8") as f:
        json.dump(limits, f, indent=2)


def check_and_update_limit(shop: str, new_rows: int) -> dict:
    limits = load_limits()
    month = _current_month()
    entry = limits.get(shop, {})

    # Сбрасываем счётчик если наступил новый месяц
    if not isinstance(entry, dict) or entry.get("month") != month:
        entry = {"used": 0, "month": month}

    current_usage = entry["used"]

    if current_usage + new_rows > FREE_TIER_LIMIT:
        return {
            "allowed": False,
            "limit": FREE_TIER_LIMIT,
            "used": current_usage,
            "requested": new_rows,
        }

    entry["used"] = current_usage + new_rows
    limits[shop] = entry
    save_limits(limits)

    return {"allowed": True}
