import hashlib
import json
import os
import time
from typing import Optional


TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), "mapping_templates.json")

# Module-level — шаблоны маппинга живут весь процесс
_templates_cache: dict = {}


def load_templates() -> dict:
    global _templates_cache
    if _templates_cache:
        return _templates_cache
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                _templates_cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            _templates_cache = {}
    return _templates_cache


def save_templates(templates: dict):
    global _templates_cache
    _templates_cache = templates
    try:
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _headers_fingerprint(headers: list[str]) -> str:
    normalized = sorted(h.lower().strip() for h in headers if h.strip())
    return hashlib.md5("|".join(normalized).encode("utf-8")).hexdigest()


def _fuzzy_match_headers(csv_headers: list[str], template_headers: list[str]) -> float:
    csv_set = set(h.lower().strip() for h in csv_headers if h.strip())
    template_set = set(h.lower().strip() for h in template_headers if h.strip())
    if not template_set:
        return 0.0
    overlap = len(csv_set & template_set)
    union = len(csv_set | template_set)
    return overlap / union if union > 0 else 0.0


def save_template(shop: str, supplier_name: str, headers: list[str], column_map: dict, tone: str) -> str:
    templates = load_templates()
    fp = _headers_fingerprint(headers)
    templates[fp] = {
        "shop": shop,
        "supplier_name": supplier_name,
        "headers": headers,
        "column_map": column_map,
        "tone_default": tone,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "usage_count": 0,
    }
    save_templates(templates)
    return fp


def find_matching_template(headers: list[str], shop: str = "", threshold: float = 0.7) -> Optional[dict]:
    templates = load_templates()
    best_score = threshold
    best_match = None
    for fp, tmpl in templates.items():
        if shop and tmpl.get("shop") != shop:
            continue
        score = _fuzzy_match_headers(headers, tmpl["headers"])
        if score > best_score:
            best_score = score
            best_match = dict(tmpl)
            best_match["match_score"] = score
            best_match["fingerprint"] = fp
    return best_match


def increment_usage(fingerprint: str):
    templates = load_templates()
    if fingerprint in templates:
        templates[fingerprint]["usage_count"] += 1
        save_templates(templates)


def list_templates(shop: str) -> list[dict]:
    templates = load_templates()
    result = []
    for fp, tmpl in templates.items():
        if tmpl.get("shop") == shop:
            result.append({
                "fingerprint": fp,
                "supplier_name": tmpl["supplier_name"],
                "headers": tmpl["headers"],
                "column_map": tmpl["column_map"],
                "created_at": tmpl["created_at"],
                "usage_count": tmpl["usage_count"],
            })
    return result


def delete_template(shop: str, fingerprint: str) -> bool:
    templates = load_templates()
    if fingerprint in templates and templates[fingerprint].get("shop") == shop:
        del templates[fingerprint]
        save_templates(templates)
        return True
    return False
