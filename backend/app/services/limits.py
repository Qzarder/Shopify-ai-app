import json
import os

LIMITS_FILE = os.path.join(os.path.dirname(__file__), "user_limits.json")

# Лимит для бесплатного тарифа (для теста поставим 150 товаров в месяц)
FREE_TIER_LIMIT = 150

def load_limits() -> dict:
    if os.path.exists(LIMITS_FILE):
        with open(LIMITS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_limits(limits: dict):
    with open(LIMITS_FILE, "w", encoding="utf-8") as f:
        json.dump(limits, f, indent=2)

def check_and_update_limit(shop: str, new_rows: int) -> dict:
    """Проверяет лимит и списывает строки, если лимит позволяет."""
    limits = load_limits()
    current_usage = limits.get(shop, 0)
    
    if current_usage + new_rows > FREE_TIER_LIMIT:
        return {
            "allowed": False, 
            "limit": FREE_TIER_LIMIT, 
            "used": current_usage,
            "requested": new_rows
        }
        
    # Если всё ок — "списываем" токены (прибавляем к использованным)
    limits[shop] = current_usage + new_rows
    save_limits(limits)
    
    return {"allowed": True}