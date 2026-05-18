"""
GitHub Models AI Provider — GPT-5/GPT-4.1 for complex reasoning tasks.
Uses the OpenAI-compatible SDK pointed at the GitHub Models endpoint.
Handles: contradiction detection, cross-section validation, advanced feedback.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from .base_provider import BaseProvider

logger = logging.getLogger("thesis_ai.providers.github")

# Model fallback chain
GITHUB_MODELS = ["gpt-5", "gpt-4.1"]
GITHUB_ENDPOINT = "https://models.github.ai/inference"


class GitHubProvider(BaseProvider):
    """GitHub Models provider — premium reasoning model for complex tasks."""

    name = "github"

    def __init__(self):
        load_dotenv()
        self.token = os.getenv("GITHUB_MODELS_TOKEN")
        self._client = None
        self._active_model = None

    def _get_client(self):
        """Lazily initialize the OpenAI-compatible client for GitHub Models."""
        if self._client is None:
            if not self.token:
                raise RuntimeError("GITHUB_MODELS_TOKEN environment variable is missing.")
            from openai import OpenAI
            self._client = OpenAI(
                base_url=GITHUB_ENDPOINT,
                api_key=self.token,
            )
        return self._client

    def _resolve_model(self, model_override: Optional[str] = None) -> str:
        """Resolve which GitHub model to use."""
        if model_override:
            return model_override
        if self._active_model:
            return self._active_model
        return GITHUB_MODELS[0]

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a JSON response using GitHub Models (OpenAI SDK).
        Tries GPT-5 first, then falls back to GPT-4.1.
        """
        if not self.token:
            return {"error": "GITHUB_MODELS_TOKEN is not set. Please configure it in your environment."}

        user_prompt = self._truncate(user_prompt, max_chars=120000)
        client = self._get_client()

        # Build the model attempt list
        primary = self._resolve_model(model_override)
        models_to_try = [primary]
        for m in GITHUB_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = ""
        for model_name in models_to_try:
            for attempt in range(2):  # 2 attempts per model
                try:
                    logger.info(f"GitHub Models request: model={model_name}, attempt={attempt + 1}")

                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.3,
                    )

                    content = response.choices[0].message.content
                    if not content:
                        raise ValueError("Empty response from GitHub Models")

                    content = self._clean_json_response(content)
                    parsed = json.loads(content)

                    # Cache which model actually worked
                    self._active_model = model_name
                    return parsed

                except json.JSONDecodeError as e:
                    last_error = f"JSON Parsing Error: {e}"
                    logger.warning(f"GitHub JSON parse error (model={model_name}, attempt={attempt + 1}): {e}")
                except Exception as e:
                    last_error = f"API Error: {e}"
                    logger.warning(f"GitHub API error (model={model_name}, attempt={attempt + 1}): {e}")

            logger.info(f"GitHub model {model_name} exhausted, trying next fallback...")

        return {"error": f"GitHub Models provider failed. Last error: {last_error}"}
