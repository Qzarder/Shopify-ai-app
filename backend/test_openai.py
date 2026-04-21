import os
from openai import OpenAI

# Проверка загрузки переменной
api_key = os.getenv("OPENAI_API_KEY")
print(f"API Key loaded: {api_key[:10]}...{api_key[-4:]}")

client = OpenAI(api_key=api_key)

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'hello' in 3 words"}],
        max_tokens=10
    )
    print(f"SUCCESS: {response.choices[0].message.content}")
except Exception as e:
    print(f"ERROR: {e}")