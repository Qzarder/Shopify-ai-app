import pandas as pd
import os
import json
import asyncio
import hashlib
import csv
from openai import OpenAI, AsyncOpenAI
from app.services.state import processing_status

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SHOPIFY_FIELDS = ["Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags", "Published", "Option1 Name", "Option1 Value", "Variant SKU", "Variant Price", "Image Src"]

# --- БРОНЕБОЙНЫЙ ЗАГРУЗЧИК CSV (Чинит сломанные файлы) ---
def advanced_robust_loader(file_path: str) -> pd.DataFrame:
    with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
        lines = [line.strip() for line in f if line.strip()]
        
    if not lines:
        return pd.DataFrame()
        
    cleaned_lines = []
    for line in lines:
        # Чиним баг Excel (когда вся строка обернута в кавычки)
        if line.startswith('"') and line.endswith('"') and '","' not in line:
            line = line[1:-1].replace('""', '"')
        cleaned_lines.append(line)
        
    try:
        # Пытаемся понять, чем разделен файл (запятая, точка с запятой и т.д.)
        dialect = csv.Sniffer().sniff(cleaned_lines[0][:1024], delimiters=',;\t|')
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ','
        
    reader = csv.reader(cleaned_lines, delimiter=delimiter)
    rows = list(reader)
    header = [str(c).strip() for c in rows[0]]
    expected_len = len(header)
    
    normalized_rows = []
    for row in rows[1:]:
        if len(row) > expected_len:
            # Если колонок больше чем надо (лишние запятые) — сливаем их в последнюю ячейку, ничего не удаляя!
            extra = delimiter.join(row[expected_len-1:])
            row = row[:expected_len-1] + [extra]
        elif len(row) < expected_len:
            # Если не хватает — добиваем пустыми
            row = row + [""] * (expected_len - len(row))
        normalized_rows.append(row)
        
    df = pd.DataFrame(normalized_rows, columns=header).fillna("")
    return df
# --------------------------------------------------------

# --- ЛОГИКА КЭШИРОВАНИЯ ---
CACHE_FILE = os.path.join(os.path.dirname(__file__), "html_cache.json")

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def generate_cache_key(merchant_id: str, title: str, desc: str) -> str:
    text_to_hash = f"{merchant_id}_{str(title)}_{str(desc)}"
    return hashlib.md5(text_to_hash.encode('utf-8')).hexdigest()
# --------------------------

def identify_columns(df_sample: pd.DataFrame) -> dict:
    sample_json = df_sample.to_json(orient="records")
    prompt = f"""
    Analyze this CSV sample from a supplier and map its columns to Shopify standard fields.
    Shopify fields: {SHOPIFY_FIELDS}
    Sample data: {sample_json}
    Return ONLY a JSON object where keys are Shopify fields and values are the corresponding column names from the sample.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    return json.loads(response.choices[0].message.content)

async def clean_and_format_html_async(title: str, raw_description: str, sem: asyncio.Semaphore, tov: str) -> str:
    async with sem:
        title_str = str(title) 
        desc_str = str(raw_description) 
        
        selected_tov = tov 
        
        tov_instructions = {
            "tech": "Act as a technical expert. Focus on specifications, hardware differences, compatibility, and performance. Use professional terminology.",
            "beauty": "Act as a high-end fashion and beauty editor. Focus on aesthetics, sensory experience, brand prestige, and results. Use luxurious language.",
            "sales": "Act as a direct-response copywriter. Focus on highlighting the customer's problem and how this product solves it. Use engaging, benefit-driven language.",
            "auto": "Analyze the product title and description. Automatically determine its niche and adapt your tone of voice perfectly to match that industry's standards."
        }
        
        current_tov = tov_instructions.get(selected_tov, tov_instructions["auto"])
        
        prompt = f"""
        You are an elite e-commerce copywriter for a top-tier Shopify store.
        Rewrite the raw supplier data into a highly converting, SEO-friendly product description.
        
        Tone of Voice Instruction: {current_tov}
        
        Product Title: {title_str}
        Raw Supplier Description: {desc_str}
        
        Rules:
        1. Write a beautiful, coherent 2-3 paragraph description that highlights the product's value.
        2. If the raw description is just random words or poor English, use the Product Title to create a realistic and engaging description.
        3. Include a bulleted list of 3-4 key features.
        4. Do NOT invent fake technical specifications.
        5. Output ONLY the final raw HTML using <p>, <ul>, <li>, <strong> tags. No markdown blocks like ```html.
        """
        
        try:
            response = await aclient.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert Shopify copywriter. Return only HTML."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6 
            )
            content = response.choices[0].message.content.strip()
            clean_content = content.replace("```html", "").replace("```", "").replace("\n", "")
            return clean_content.strip()
        except Exception:
            return str(raw_description)

async def process_all_descriptions(df: pd.DataFrame, file_id: str, merchant_id: str, tov: str):
    sem = asyncio.Semaphore(15) 
    cache = load_cache() 
    
    async def task_wrapper(index, title, desc, tov):
        title_str = str(title)
        desc_str = str(desc)
        
        cache_key = generate_cache_key(merchant_id, title_str, desc_str)
        
        if cache_key in cache:
            clean_html = cache[cache_key]
        else:
            clean_html = await clean_and_format_html_async(title_str, desc_str, sem, tov)
            cache[cache_key] = clean_html
            
        return index, clean_html

    tasks = [task_wrapper(index, row["Title"], row.get("Body (HTML)", ""), tov) for index, row in df.iterrows()]
    
    completed = 0
    for future in asyncio.as_completed(tasks):
        index, clean_html = await future
        df.at[index, "Body (HTML)"] = clean_html
        completed += 1
        processing_status[file_id]["current"] = completed
        
    save_cache(cache)

def process_csv_file(input_path: str, output_path: str, file_id: str, tov: str="auto"):
    current_merchant_id = "merchant_test_001" 
    
    try:
        # ИСПОЛЬЗУЕМ НАШ НОВЫЙ БРОНЕБОЙНЫЙ ЗАГРУЗЧИК
        df = advanced_robust_loader(input_path)
        total_rows = len(df)
        
        processing_status[file_id] = {"current": 0, "total": total_rows, "status": "mapping"}
        
        column_map = identify_columns(df.head(3))
        print(f"Detected mapping: {column_map}")
        
        new_df = pd.DataFrame(columns=SHOPIFY_FIELDS)
        for shopify_field, supplier_field in column_map.items():
            if supplier_field in df.columns:
                new_df[shopify_field] = df[supplier_field]
                
        if "Title" in new_df.columns:
            new_df["Handle"] = new_df["Title"].str.lower().replace(r'[^a-z0-9]+', '-', regex=True)
            
        processing_status[file_id]["status"] = "cleaning" 
        print(f"Starting TURBO AI for merchant {current_merchant_id}...")
        
        asyncio.run(process_all_descriptions(new_df, file_id, current_merchant_id, tov))
            
        new_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        
        processing_status[file_id]["status"] = "completed"
        print(f"Done! Saved to {output_path}")
        
    except Exception as e:
        processing_status[file_id] = {"current": 0, "total": 0, "status": "error", "error": str(e)}
        print(f"Error processing file: {e}")