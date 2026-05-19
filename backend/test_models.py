"""Test which model name format works with the google-genai SDK."""
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Test model names
test_models = [
    "gemini-2.5-flash",
    "models/gemini-2.5-flash",
    "gemini-2.0-flash",
    "models/gemini-2.0-flash",
]

for model_name in test_models:
    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction="Return JSON",
        )
        resp = client.models.generate_content(
            model=model_name,
            contents="Say hello as JSON: {\"greeting\": \"hello\"}",
            config=config,
        )
        print(f"OK: {model_name} -> {resp.text[:80]}")
    except Exception as e:
        print(f"FAIL: {model_name} -> {str(e)[:120]}")
