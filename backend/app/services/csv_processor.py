import asyncio
import csv
import hashlib
import json
import os

import pandas as pd
from openai import AsyncOpenAI, OpenAI

from app.services.state import processing_status

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    for row in rows[1:]:
        if len(row) > expected_len:
            extra = delimiter.join(row[expected_len - 1 :])
            row = row[: expected_len - 1] + [extra]
        elif len(row) < expected_len:
            row = row + [""] * (expected_len - len(row))
        normalized_rows.append(row)

    return pd.DataFrame(normalized_rows, columns=header).fillna("")


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def generate_cache_key(merchant_id: str, title: str, desc: str, tone: str) -> str:
    text_to_hash = f"{merchant_id}_{str(title)}_{str(desc)}_{str(tone)}"
    return hashlib.md5(text_to_hash.encode("utf-8")).hexdigest()


def identify_columns(df_sample: pd.DataFrame) -> dict:
    sample_json = df_sample.to_json(orient="records")
    prompt = f"""
    Analyze this CSV sample and map its columns to Shopify fields: {SHOPIFY_FIELDS}
    Sample data: {sample_json}

    Return ONLY a JSON object.
    Rules:
    - Each value must be either one source column name string from the sample or null.
    - Never return arrays/lists.
    - If several columns look possible, choose the single best match.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


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


async def clean_and_format_html_async(title: str, raw_description: str, sem: asyncio.Semaphore, tone: str) -> str:
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

        try:
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
            return str(raw_description)


async def process_all_descriptions(df: pd.DataFrame, file_id: str, merchant_id: str, tone: str):
    sem = asyncio.Semaphore(15)
    cache = load_cache()

    async def task_wrapper(index, title, desc, current_tone):
        cache_key = generate_cache_key(merchant_id, title, desc, current_tone)
        if cache_key in cache:
            return index, cache[cache_key]
        clean_html = await clean_and_format_html_async(title, desc, sem, current_tone)
        cache[cache_key] = clean_html
        return index, clean_html

    tasks = [
        task_wrapper(index, row["Title"], row.get("Body (HTML)", ""), tone)
        for index, row in df.iterrows()
    ]

    completed = 0
    for future in asyncio.as_completed(tasks):
        index, clean_html = await future
        df.at[index, "Body (HTML)"] = clean_html
        completed += 1
        processing_status[file_id]["current"] = completed

    save_cache(cache)


def process_csv_file(input_path: str, output_path: str, file_id: str, merchant_id: str, tone: str = "Neutral & Professional"):
    try:
        df = advanced_robust_loader(input_path)
        total_rows = len(df)
        processing_status[file_id] = {"current": 0, "total": total_rows, "status": "mapping"}

        column_map = identify_columns(df.head(3))
        if not isinstance(column_map, dict):
            raise ValueError(f"Column map must be a JSON object, got {type(column_map).__name__}")

        print(f"DEBUG column_map for {file_id}: {column_map}")

        new_df = pd.DataFrame(columns=SHOPIFY_FIELDS)
        for shopify_field, supplier_field in column_map.items():
            apply_column_mapping(df, new_df, shopify_field, supplier_field)

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
        asyncio.run(process_all_descriptions(new_df, file_id, merchant_id, tone))

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
