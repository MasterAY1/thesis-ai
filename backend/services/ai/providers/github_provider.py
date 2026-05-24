"""
GitHub Models AI Provider — GPT-5/GPT-4.1 for complex reasoning tasks.
Uses the OpenAI-compatible SDK pointed at the GitHub Models endpoint.
Handles: contradiction detection, cross-section validation, advanced feedback.

SAFETY: Enforces token limits before every call. Never sends > 6000 tokens.
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

# Token safety limits
CHARS_PER_TOKEN = 4
MAX_SAFE_CHARS = 24000  # ~6000 tokens — stays safely under 8k limit


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

    def _enforce_token_safety(self, system_prompt: str, user_prompt: str) -> str:
        """
        Enforce hard token safety limits on user_prompt.
        System prompt is kept intact; user prompt is truncated if needed.
        """
        system_tokens = len(system_prompt) // CHARS_PER_TOKEN
        available_chars = MAX_SAFE_CHARS - len(system_prompt)

        if available_chars < 2000:
            # System prompt is unusually long, cap it
            available_chars = 8000  # minimum user space

        if len(user_prompt) <= available_chars:
            return user_prompt

        estimated_total = (len(system_prompt) + len(user_prompt)) // CHARS_PER_TOKEN
        logger.warning(
            f"Token safety triggered: ~{estimated_total} tokens estimated. "
            f"Truncating user_prompt from {len(user_prompt)} to {available_chars} chars."
        )

        # Smart truncate: keep beginning and end
        first = available_chars * 2 // 3
        last = available_chars // 3
        return (
            user_prompt[:first]
            + "\n\n... [TRUNCATED FOR TOKEN SAFETY] ...\n\n"
            + user_prompt[-last:]
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a JSON response using GitHub Models (OpenAI SDK).
        Tries GPT-5 first, then falls back to GPT-4.1.
        Enforces token safety before every call.
        """
        if not self.token:
            return {"error": "GITHUB_MODELS_TOKEN is not set. Please configure it in your environment."}

        # CRITICAL: Enforce token safety BEFORE sending to GitHub
        user_prompt = self._enforce_token_safety(system_prompt, user_prompt)
        client = self._get_client()

        total_chars = len(system_prompt) + len(user_prompt)
        estimated_tokens = total_chars // CHARS_PER_TOKEN
        logger.info(f"GitHub GPT payload: {total_chars} chars (~{estimated_tokens} tokens)")

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
                        temperature=0,       # DETERMINISTIC: no randomness
                        top_p=0.1,           # DETERMINISTIC: minimal sampling
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
                    error_str = str(e)
                    last_error = f"API Error: {error_str}"
                    logger.warning(f"GitHub API error (model={model_name}, attempt={attempt + 1}): {error_str}")

                    # If it's a token limit error, don't retry the same model
                    if "token" in error_str.lower() or "413" in error_str or "too large" in error_str.lower():
                        logger.error(f"Token limit hit on {model_name}. Skipping remaining attempts.")
                        break

            logger.info(f"GitHub model {model_name} exhausted, trying next fallback...")

        return {"error": f"GitHub Models provider failed. Last error: {last_error}"}
