"""
Gemini AI Provider — Deterministic Mode

CRITICAL SETTINGS FOR SCORING CONSISTENCY:
  temperature = 0      → no randomness
  top_p = 0.1          → minimal sampling
  top_k = 1            → greedy decoding
  response_mime_type   → application/json (strict)

Same prompt → same output. Every time.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .base_provider import BaseProvider

logger = logging.getLogger("thesis_ai.providers.gemini")

# Model fallback chain
GEMINI_MODELS = [
    "models/gemini-2.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-1.5-flash",
]


class GeminiProvider(BaseProvider):
    """Google Gemini Flash provider — deterministic mode for grading consistency."""

    name = "gemini"

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        self._client = None
        self._active_model = None

    def _get_client(self):
        """Lazily initialize the Gemini client."""
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY environment variable is missing.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _resolve_model(self, model_override: Optional[str] = None) -> str:
        """Resolve which Gemini model to use."""
        if model_override:
            return model_override
        if self._active_model:
            return self._active_model
        env_model = os.getenv("MODEL_NAME", "")
        if env_model:
            if not env_model.startswith("models/"):
                env_model = f"models/{env_model}"
            return env_model
        return GEMINI_MODELS[0]

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a JSON response using Gemini in DETERMINISTIC mode.

        Settings enforced:
          temperature = 0   → greedy, no randomness
          top_p = 0.1       → minimal nucleus sampling
          top_k = 1         → pick the single most likely token
          response_mime_type = application/json → strict JSON output

        Thread-safe — can be called from asyncio.to_thread().
        """
        if not self.api_key:
            return {"error": "GEMINI_API_KEY is not set. Please configure it in your environment."}

        user_prompt = self._truncate(user_prompt)
        client = self._get_client()

        from google.genai import types
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=system_prompt,
            temperature=0,       # DETERMINISTIC: no randomness
            top_p=0.1,           # DETERMINISTIC: minimal sampling
            top_k=1,             # DETERMINISTIC: greedy decoding
        )

        primary = self._resolve_model(model_override)
        models_to_try = [primary]
        for m in GEMINI_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = ""
        for model_name in models_to_try:
            for attempt in range(2):
                try:
                    logger.info(f"Gemini request: model={model_name}, attempt={attempt + 1}, temp=0")

                    response = client.models.generate_content(
                        model=model_name,
                        contents=user_prompt,
                        config=config,
                    )

                    content = response.text
                    if not content:
                        raise ValueError("Empty response from Gemini")

                    content = self._clean_json_response(content)
                    parsed = json.loads(content)

                    self._active_model = model_name
                    return parsed

                except json.JSONDecodeError as e:
                    last_error = f"JSON Parsing Error: {e}"
                    logger.warning(f"Gemini JSON parse error (model={model_name}, attempt={attempt + 1}): {e}")
                except Exception as e:
                    last_error = f"API Error: {e}"
                    logger.warning(f"Gemini API error (model={model_name}, attempt={attempt + 1}): {e}")

            logger.info(f"Gemini model {model_name} exhausted, trying next fallback...")

        return {"error": f"Gemini provider failed. Last error: {last_error}"}

    async def generate_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async wrapper — offloads blocking call to thread pool."""
        import asyncio
        return await asyncio.to_thread(self.generate, system_prompt, user_prompt, model_override)
