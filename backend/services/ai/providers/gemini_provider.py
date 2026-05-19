"""
Gemini AI Provider — Google's fast/cheap model for lightweight tasks.
Handles: section splitting, quick grading, formatting checks, rubric evaluation.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .base_provider import BaseProvider

logger = logging.getLogger("thesis_ai.providers.gemini")

# Model fallback chain — tries each in order until one works
# The models/ prefix is required by the google-genai SDK
GEMINI_MODELS = [
    "models/gemini-2.5-flash",       # Primary: best quality
    "models/gemini-2.0-flash",       # Fallback 1: stable
    "models/gemini-3.1-flash-lite",  # Fallback 2: fast/cheap
]


class GeminiProvider(BaseProvider):
    """Google Gemini Flash provider — default fast/cheap model."""

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
            # Ensure the models/ prefix is present
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
        Generate a JSON response using Gemini.
        Tries the primary model first, then falls back through GEMINI_MODELS.
        """
        if not self.api_key:
            return {"error": "GEMINI_API_KEY is not set. Please configure it in your environment."}

        user_prompt = self._truncate(user_prompt)
        client = self._get_client()

        from google.genai import types
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=system_prompt,
        )

        # Build the model attempt list
        primary = self._resolve_model(model_override)
        models_to_try = [primary]
        for m in GEMINI_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = ""
        for model_name in models_to_try:
            for attempt in range(2):  # 2 attempts per model
                try:
                    logger.info(f"Gemini request: model={model_name}, attempt={attempt + 1}")

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

                    # Cache which model actually worked
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
