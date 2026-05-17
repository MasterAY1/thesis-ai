import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

def truncate_text(text: str, max_chars: int = 300000) -> str:
    """
    Intelligently truncates extremely large documents before sending.
    Gemini 2.5 Flash can handle 1M tokens, but we cap at 300k characters (~75k tokens)
    to ensure fast responses and prevent massive payloads.
    """
    if len(text) <= max_chars:
        return text
    # Keep the first part and the last part, assuming middle might be less relevant for structural extraction
    half = max_chars // 2
    return text[:half] + "\n\n... [EXTREME LENGTH CONTENT TRUNCATED] ...\n\n" + text[-half:]

def generate_json_response(system_prompt: str, user_prompt: str, model: str = None) -> dict:
    """
    Centralized API wrapper using Google Gemini API.
    Forces JSON output, validates it, and retries once if invalid.
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not model:
        model = os.getenv("MODEL_NAME", "gemini-2.5-flash")
        
    if not api_key:
        print("Warning: GEMINI_API_KEY environment variable is missing.")
        return {"error": "API key missing. Please set GEMINI_API_KEY in backend/.env"}

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return {"error": f"Failed to initialize Gemini client: {str(e)}"}

    # Truncate user prompt if it's too large
    user_prompt = truncate_text(user_prompt)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=system_prompt,
    )

    # Retry logic (1 retry, max 2 attempts total)
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=config,
            )
            
            content = response.text
            if not content:
                 raise ValueError("Empty response from Gemini")
            
            # Clean up potential markdown blocks if the model ignored response_mime_type
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            # Basic JSON validation
            parsed_json = json.loads(content.strip())
            return parsed_json
            
        except json.JSONDecodeError as e:
            error_msg = f"JSON Parsing Error: {e}"
            print(f"JSON parsing error on attempt {attempt + 1}: {e}")
        except Exception as e:
            error_msg = f"Network/API Error: {e}"
            print(f"API error on attempt {attempt + 1}: {e}")
            
        if attempt == 1:
            return {"error": f"LLM API Failed. Last error: {error_msg}"}

    return {"error": "Unknown error occurred."}
