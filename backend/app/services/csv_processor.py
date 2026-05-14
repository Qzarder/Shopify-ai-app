import asyncio
import csv
import hashlib
import json
import os

import pandas as pd
from openai import AsyncOpenAI, OpenAI

from app.services.state import processing_status
from app.services.mapping_templates import find_matching_template, save_template, increment_usage

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set!")
print(f"[DEBUG] OpenAI API Key loaded: {api_key[:15]}...")

client = OpenAI(api_key=api_key)
aclient = AsyncOpenAI(api_key=api_key)

SHOPIFY_FIELDS = [
    "Handle",
    "Title",
    "Body (HTML)",
    "Vendor",
    "Type",
    "Tags",
    "Published",
    "Option1 Name",
    "Option1 Value",
    "Variant SKU",
    "Variant Price",
    "Image Src",
]

CACHE_FILE = os.path.join(os.path.dirname(__file__), "html_cache.json")

TONE_ALIASES = {
    "neutral": "Neutral & Professional",
    "enthusiastic": "Enthusiastic & Sales-driven",
    "luxury": "Luxury & Elegant",
    "playful": "Fun & Playful",
    "minimalist": "Minimalist & Direct",
}

STYLE_PROFILES = {
    "Neutral & Professional": {
        "role": "Balanced E-commerce Copywriter",
        "instructions": "Write a clear, informative, and stable description. Use a friendly but professional tone. Focus on reliability and quality. Structure: Intro paragraph -> 3-4 bullet points -> Brief closing.",
        "forbidden": ["revolutionary", "insane", "magic", "best ever"],
    },
    "Enthusiastic & Sales-driven": {
        "role": "Direct-Response Copywriter",
        "instructions": "Focus on high energy, the joy of using the product, and the 'Why you need this NOW' factor. Use punchy, persuasive sentences. Structure: Catchy hook -> Enthusiastic body -> Benefit-driven bullet points.",
        "forbidden": ["standard", "maybe", "item", "average"],
    },
    "Luxury & Elegant": {
        "role": "Visual & Sensory Copywriter",
        "instructions": "Focus on deep details, textures, materials, and appearance. Paint a picture with words using elegant, flowing language. NO bullet points. Use 3 long, rich paragraphs with <strong> for highlights.",
        "forbidden": ["cheap", "fast", "click here", "features", "specifications"],
    },
    "Fun & Playful": {
        "role": "Creative & Enthusiastic Storyteller",
        "instructions": "Use humor, emojis (sparingly), and high-energy adjectives. Focus on the joy of using the product. Structure: Catchy hook -> Enthusiastic body -> Fun bullet points.",
        "forbidden": ["technical specifications", "standard", "moreover", "hereby"],
    },
    "Minimalist & Direct": {
        "role": "Technical Systems Engineer",
        "instructions": "Focus on hardware specs, compatibility, and performance data. Use dry, precise, and direct language. Structure: 1 brief intro sentence -> Detailed <ul> list of specs.",
        "forbidden": ["beautiful", "elegant", "life-changing", "amazing"],
    },
}


def advanced_robust_loader(file_path: str) -> pd.DataFrame:
    with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return pd.DataFrame()

    cleaned_lines = []
    for line in lines:
        if line.startswith('"') and line.endswith('"') and '","' not in line:
            line = line[1:-1].replace('""', '"')
        cleaned_lines.append(line)
    try:
        dialect = csv.Sniffer().sniff(cleaned_lines[0][:1024], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    reader = csv.reader(cleaned_lines, delimiter=delimiter)
    rows = list(reader)
    header = [str(cell).strip() for cell in rows[0]]
    expected_len = len(header)

    normalized_rows = []
    warnings = []
    row_num = 0
    for row in rows[1:]:
        row_num += 1
        if len(row) > expected_len:
            overflow = row[expected_len:]
            row = row[:expected_len]
            salvaged = False
            for extra_field in overflow:
                clean = extra_field.strip()
                if clean.lower() in {"nan", "none", "null", "in_stock", "out_of_stock",
                                      "backorder", "discontinued", "pre_order", "limited_stock",
                                      "in", "out"}:
                    continue
                if clean.startswith("http"):
                    row[-1] = clean
                    salvaged = True
                    break
            if salvaged:
                warnings.append(f"Row {row_num}: salvaged image URL from overflow columns")
            else:
                warnings.append(f"Row {row_num}: {len(overflow)} extra columns truncated")
        elif len(row) < expected_len:
            row = row + [""] * (expected_len - len(row))
        normalized_rows.append(row)
    if warnings:
        print(f"WARNINGS for {file_path}:")
        for w in warnings[:5]:
            print(f"  {w}")
        if len(warnings) > 5:
            print(f"  ... and {len(warnings) - 5} more")

    return pd.DataFrame(normalized_rows, columns=header).fillna("")


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)



IGNORED_FOR_FINGERPRINT = {'price', 'cost', 'compare at price', 'inventory', 'stock', 'quantity'}

EXTRA_FINGERPRINT_FIELDS = {'sku', 'variant sku', 'color', 'colour', 'size', 'material', 'weight', 'option', 'variant'}

SHOPIFY_IGNORED_FOR_FINGERPRINT = {
    "Variant Price", "Variant Compare At Price",
    "Variant Inventory Qty", "Variant Weight",
    "Image Src",
}


def generate_fingerprint(shop: str, source_row_dict: dict, column_map: dict, tone: str) -> str:
    parts = [str(shop), str(tone)]

    for shopify_field, source_col in column_map.items():
        if shopify_field in SHOPIFY_IGNORED_FOR_FINGERPRINT:
            continue
        if isinstance(source_col, list):
            for col in source_col:
                if col in source_row_dict:
                    val = str(source_row_dict[col]).strip().lower()
                    parts.append(f"map_{shopify_field}={val}")
        elif isinstance(source_col, str) and source_col in source_row_dict:
            val = str(source_row_dict[source_col]).strip().lower()
            parts.append(f"map_{shopify_field}={val}")

    for field, value in source_row_dict.items():
        field_lower = field.lower()
        if any(ignored == field_lower for ignored in IGNORED_FOR_FINGERPRINT):
            continue
        if any(extra in field_lower for extra in EXTRA_FINGERPRINT_FIELDS):
            val = str(value).strip().lower()
            parts.append(f"meta_{field_lower}={val}")

    parts.sort()
    fingerprint_text = json.dumps(parts, ensure_ascii=False)
    return hashlib.md5(fingerprint_text.encode("utf-8")).hexdigest()


def identify_columns(df_sample: pd.DataFrame) -> dict:
    csv_columns = list(df_sample.columns)
    sample_json = df_sample.head(2).to_json(orient="records")
    prompt = f"""
    You have a CSV with these columns: {json.dumps(csv_columns)}.
    Here is a sample of the first 2 rows: {sample_json}

    Map the CSV columns to Shopify product fields from this list:
    {json.dumps(SHOPIFY_FIELDS)}

    RETURN A FLAT JSON OBJECT where keys are Shopify field names (strings)
    and values are CSV column names (strings).
    Use null for fields that have no match.
    NEVER return arrays, nested objects, or row data.

    Example correct response:
    {{"Title": "Name", "Body (HTML)": "Description", "Vendor": null, "Type": null, "Tags": null, "Published": null, "Option1 Name": null, "Option1 Value": null, "Variant SKU": null, "Variant Price": null, "Image Src": null}}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    if not isinstance(result, dict):
        raise ValueError(f"AI returned {type(result).__name__} instead of dict")
    return result


def normalize_supplier_field(value):
    if isinstance(value, list):
        cleaned = []
        for item in value:
            if isinstance(item, (list, dict)):
                continue
            text = str(item).strip()
            if text:
                cleaned.append(text)
        return cleaned

    if isinstance(value, dict) or value is None:
        return None

    text = str(value).strip()
    return text or None


def combine_source_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    return (
        df[columns]
        .fillna("")
        .astype(str)
        .apply(
            lambda row: ", ".join(
                value.strip()
                for value in row
                if value and value.strip() and value.strip().lower() not in {"nan", "none", "null"}
            ),
            axis=1,
        )
    )


def apply_column_mapping(df: pd.DataFrame, new_df: pd.DataFrame, shopify_field: str, supplier_field):
    normalized_field = normalize_supplier_field(supplier_field)

    if isinstance(normalized_field, list):
        valid_columns = [column for column in normalized_field if column in df.columns]
        if not valid_columns:
            return
        if shopify_field == "Tags" and len(valid_columns) > 1:
            new_df[shopify_field] = combine_source_columns(df, valid_columns)
        else:
            new_df[shopify_field] = df[valid_columns[0]]
        return

    if normalized_field and normalized_field in df.columns:
        new_df[shopify_field] = df[normalized_field]


async def clean_and_format_html_async(title: str, raw_description: str, sem: asyncio.Semaphore, tone: str, gen_seo: bool = False, gen_alt: bool = False) -> dict | str:
    async with sem:
        title_str = str(title)
        desc_str = "" if str(raw_description).lower() in ["nan", "none", "null"] else str(raw_description)
        normalized_tone = TONE_ALIASES.get(str(tone).strip().lower(), tone)
        profile = STYLE_PROFILES.get(normalized_tone, STYLE_PROFILES["Neutral & Professional"])

        prompt = f"""
        Act as a {profile['role']}. Rewrite this product description.
        Product: {title_str}
        Source: {desc_str}

        STRICT RULES:
        1. Style: {profile['instructions']}
        2. Forbidden words: {", ".join(profile['forbidden'])}
        3. Never start with "{title_str} is..." or "Introducing...".
        4. Output ONLY raw HTML (p, strong, ul, li).
        """

        if gen_seo or gen_alt:
            prompt += "\n\nALSO return a JSON with these fields:\n"
            prompt += '{"body": "<HTML description>", '
            if gen_seo:
                prompt += '"seo_title": "<55 char SEO title>", "seo_desc": "<160 char meta description>", '
            if gen_alt:
                prompt += '"alt_text": "<image alt text>", '
            prompt += "}"
            prompt += "\nReturn ONLY the JSON, no markdown wrappers."

        try:
            if gen_seo or gen_alt:
                response = await aclient.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Professional unique copywriter. Seed: {hash(title_str) % 1000}. Output valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.8,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content.strip()
                result = json.loads(content)
                result["body"] = (
                    result.get("body", "")
                    .replace("```html", "")
                    .replace("```", "")
                    .replace("\n", " ")
                    .replace("\r", "")
                    .strip()
                )
                return result
            else:
                response = await aclient.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"Professional unique copywriter. Seed: {hash(title_str) % 1000}"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.8,
                )
                content = response.choices[0].message.content.strip()
                clean_content = (
                    content.replace("```html", "")
                    .replace("```", "")
                    .replace("\n", " ")
                    .replace("\r", "")
                )
                return clean_content.strip()
        except Exception:
            return {"body": str(raw_description), "seo_title": title_str, "seo_desc": "", "alt_text": ""} if gen_seo or gen_alt else str(raw_description)


async def process_all_descriptions(df: pd.DataFrame, file_id: str, shop: str, tone: str, gen_seo: bool = False, gen_alt: bool = False):
    sem = asyncio.Semaphore(15)
    cache = load_cache()

    async def task_wrapper(index, title, desc, current_tone, fingerprint):
        cache_key = fingerprint
        if cache_key in cache:
            return index, cache[cache_key]
        result = await clean_and_format_html_async(title, desc, sem, current_tone, gen_seo, gen_alt)
        cache[cache_key] = result
        return index, result

    tasks = [
        task_wrapper(index, row["Title"], row.get("Body (HTML)", ""), tone, row["_fingerprint"])
        for index, row in df.iterrows()
    ]

    if gen_seo:
        df["SEO Title"] = ""
        df["SEO Description"] = ""
    if gen_alt:
        df["Image Alt Text"] = ""

    completed = 0
    for future in asyncio.as_completed(tasks):
        index, result = await future
        if isinstance(result, dict):
            df.at[index, "Body (HTML)"] = result.get("body", "")
            if gen_seo:
                df.at[index, "SEO Title"] = result.get("seo_title", "")
                df.at[index, "SEO Description"] = result.get("seo_desc", "")
            if gen_alt:
                df.at[index, "Image Alt Text"] = result.get("alt_text", "")
        else:
            df.at[index, "Body (HTML)"] = result
        completed += 1
        processing_status[file_id]["current"] = completed

    save_cache(cache)


def process_csv_file(input_path: str, output_path: str, file_id: str, shop: str, tone: str = "Neutral & Professional", supplier_name: str = "", gen_seo: bool = False, gen_alt: bool = False):
    try:
        source_df = advanced_robust_loader(input_path)
        total_rows = len(source_df)
        processing_status[file_id] = {"current": 0, "total": total_rows, "status": "mapping"}

        csv_headers = list(source_df.columns)

        column_map = None
        template_fp = None
        if csv_headers:
            matched = find_matching_template(csv_headers, shop)
            if matched:
                column_map = matched["column_map"]
                template_fp = matched["fingerprint"]
                if os.getenv("DEBUG"):
                    print(f"DEBUG template matched for {file_id}: {matched['supplier_name']} (score={matched['match_score']:.0%})")
            else:
                if os.getenv("DEBUG"):
                    print(f"DEBUG no template match for {file_id}, using AI mapping")

        if column_map is None:
            column_map = identify_columns(source_df.head(3))
            if supplier_name:
                save_template(shop, supplier_name, csv_headers, column_map, tone)
                if os.getenv("DEBUG"):
                    print(f"DEBUG saved template for {file_id}: {supplier_name}")

        if template_fp:
            increment_usage(template_fp)

        if not isinstance(column_map, dict):
            raise ValueError(f"Column map must be a JSON object, got {type(column_map).__name__}")

        print(f"DEBUG column_map for {file_id}: {column_map}")

        fingerprints = []
        for _, row in source_df.iterrows():
            source_row_dict = row.to_dict()
            fp = generate_fingerprint(shop, source_row_dict, column_map, tone)
            fingerprints.append(fp)
        if os.getenv("DEBUG"):
            print(f"DEBUG fingerprints for {file_id}: {len(fingerprints)} unique={len(set(fingerprints))}")

        new_df = pd.DataFrame(columns=SHOPIFY_FIELDS)

        for shopify_field, supplier_field in column_map.items():
            apply_column_mapping(source_df, new_df, shopify_field, supplier_field)

        new_df["_fingerprint"] = fingerprints

        if "Title" in new_df.columns:
            new_df["Handle"] = (
                new_df["Title"]
                .fillna("")
                .astype(str)
                .str.lower()
                .replace(r"[^a-z0-9]+", "-", regex=True)
                .str.strip("-")
            )

        processing_status[file_id]["status"] = "cleaning"
        asyncio.run(process_all_descriptions(new_df, file_id, shop, tone, gen_seo, gen_alt))

        if "_fingerprint" in new_df.columns:
            new_df = new_df.drop(columns=["_fingerprint"])

        new_df.to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig",
            quoting=csv.QUOTE_ALL,
            escapechar="\\",
        )

        processing_status[file_id]["status"] = "completed"
    except Exception as e:
        processing_status[file_id] = {"current": 0, "total": 0, "status": "error", "error": str(e)}
