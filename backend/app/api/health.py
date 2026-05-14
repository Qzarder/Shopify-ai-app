import os
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    api_key = os.getenv("OPENAI_API_KEY", "")
    return {
        "status": "ok",
        "openai_key_set": bool(api_key),
    }

@router.get("/test-openai")
def test_openai():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "No API key"}
    
    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        return {"success": True, "response": response.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}

@router.get("/success")
def success():
    return {"status": "payment_success"}

@router.get("/cancel")
def cancel():
    return {"status": "payment_cancelled"}
