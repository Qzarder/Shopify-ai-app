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

def generate_cache_key(merchant_id: str, title: str, desc: str, tov: str) -> str:
    # ВОТ ЗДЕСЬ МАГИЯ: Ключ состоит из ID мерчанта + Названия + Описания + ТоВ
    # Это гарантирует, что у каждого мерчанта и для каждого стиля свой изолированный кэш
    text_to_hash = f"{merchant_id}_{str(title)}_{str(desc)}_{str(tov)}"
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

async def clean_and_format_html_async(title: str, raw_description: str, sem: asyncio.Semaphore, tone: str) -> str:
    async with sem:
        title_str = str(title) 
        desc_str = "" if str(raw_description).lower() in ["nan", "none", "null"] else str(raw_description) 
        
        # Детальные инструкции для каждого стиля
        style_profiles = {
            "neutral": {
                "role": "Balanced E-commerce Copywriter",
                "instructions": "Write a clear, informative, and stable description. Use a friendly but professional tone. Structure: Intro paragraph -> 3-4 bullet points -> Brief closing.",
                "forbidden": ["revolutionary", "insane", "magic", "best ever"]
            },
            "playful": {
                "role": "Creative & Enthusiastic Storyteller",
                "instructions": "Use humor, emojis (sparingly), and high-energy adjectives. Focus on the joy of using the product. Structure: Catchy hook -> Enthusiastic body -> Fun bullet points.",
                "forbidden": ["technical specifications", "standard", "moreover", "hereby"]
            },
            "professional": {
                "role": "Expert Industry Consultant",
                "instructions": "Use formal, authoritative language. Focus on reliability, ROI, and quality. Use sophisticated vocabulary. Structure: Executive summary style paragraphs.",
                "forbidden": ["cool", "awesome", "maybe", "stuff"]
            },
            "discriptive": { # Оставляем опечатку как во фронте для связи ключей
                "role": "Visual & Sensory Copywriter",
                "instructions": "Focus on deep details, textures, materials, and appearance. Paint a picture with words. Use NO bullet points. Use 3 long, rich paragraphs.",
                "forbidden": ["fast", "cheap", "click here", "features"]
            },
            "tech": {
                "role": "Technical Systems Engineer",
                "instructions": "Focus on hardware specs, compatibility, and performance data. Use dry, precise language. Structure: 1 brief intro sentence -> Detailed <ul> list of specs.",
                "forbidden": ["beautiful", "elegant", "life-changing", "amazing"]
            },
            "auto": {
                "role": "Versatile Marketing AI",
                "instructions": "Analyze the product title and match the industry standard tone perfectly.",
                "forbidden": ["Introducing"]
            }
        }
        profile = style_profiles.get(tone, style_profiles["auto"])
        
        prompt = f"""
        Act as a {profile['role']}. Rewrite the product data into a unique Shopify HTML description.
        
        Product: {title_str}
        Source Info: {desc_str}
        
        STRICT RULES:
        1. Tone/Style: {profile['instructions']}
        2. Forbidden words: {", ".join(profile['forbidden'])}
        3. Never start with "{title_str} is..." or "Introducing...". 
        4. Syntax: Change the sentence structure completely compared to a standard description.
        5. Output ONLY raw HTML (p, strong, ul, li). No markdown code blocks.
        """
        
        try:
            response = await aclient.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are a professional copywriter. Your goal is to be unique and avoid repetitive structures. Seed: {hash(title_str) % 1000}"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8 # Увеличили креативность
            )
            content = response.choices[0].message.content.strip()
            
            # Очистка
            clean_content = content.replace("```html", "").replace("```", "").replace('\n', ' ').replace('\r', '')
            return clean_content.strip()
        except Exception as e:
            print(f"AI Generation Error: {e}")
            return str(raw_description)

# Принимает merchant_id
async def process_all_descriptions(df: pd.DataFrame, file_id: str, merchant_id: str, tov: str):
    sem = asyncio.Semaphore(15) 
    cache = load_cache() 
    
    async def task_wrapper(index, title, desc, tov):
        title_str = str(title)
        desc_str = str(desc)
        
        # Генерируем ключ, который привязан к конкретному мерчанту и конкретному TOV
        cache_key = generate_cache_key(merchant_id, title_str, desc_str, tov)
        
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

# УБРАЛИ ЖЕСТКИЙ ХАРДКОД. Теперь функция принимает merchant_id из роута
def process_csv_file(input_path: str, output_path: str, file_id: str, merchant_id: str, tov: str="auto"):
    try:
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
        print(f"Starting TURBO AI for merchant {merchant_id}...")
        
        # Передаем merchant_id и TOV дальше в обработчик
        asyncio.run(process_all_descriptions(new_df, file_id, merchant_id, tov))
            
        new_df.to_csv(
            output_path, 
            index=False, 
            encoding="utf-8-sig", 
            quoting=csv.QUOTE_ALL,  # Оборачивает КАЖДОЕ поле в кавычки ""
            escapechar='\\'         # Экранирует спецсимволы, если они есть
        )        

        processing_status[file_id]["status"] = "completed"
        print(f"Done! Saved to {output_path}")
        
    except Exception as e:
        processing_status[file_id] = {"current": 0, "total": 0, "status": "error", "error": str(e)}
        print(f"Error processing file: {e}")