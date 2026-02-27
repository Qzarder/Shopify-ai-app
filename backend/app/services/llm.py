import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PROMPT_TEMPLATE = """
You are a product copy editor for Shopify pet supply stores.

Your task:
Turn a messy supplier product description into a clean, sellable,
Shopify-ready HTML description.

Rules:
- Do NOT mention AI, suppliers, factories, or AliExpress
- Do NOT make medical or veterinary claims
- Do NOT exaggerate or use hype language
- Use clear, neutral, natural English
- Assume the buyer is a normal pet owner, not a professional
- If the text is unclear or repetitive, clean and simplify it
- If something is missing, make a reasonable, generic assumption

Output format (HTML only):

<p><strong>Short, clear product introduction (1–2 sentences).</strong></p>

<ul>
  <li>Feature or benefit 1</li>
  <li>Feature or benefit 2</li>
  <li>Feature or benefit 3</li>
</ul>

<p>Simple closing line.</p>

Title: {title}
Description: {description}
"""

def generate_html(title: str, description: str) -> str:
    prompt = PROMPT_TEMPLATE.format(
        title=title.strip(),
        description=description.strip()
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()
