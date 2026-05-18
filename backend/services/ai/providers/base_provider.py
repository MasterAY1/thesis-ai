"""
Base AI Provider — Abstract interface all providers must implement.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("thesis_ai.providers")


class BaseProvider(ABC):
    """Abstract base class for all AI providers."""

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a prompt to the AI model and return a parsed JSON response.

        Args:
            system_prompt: The system-level instruction for the model.
            user_prompt: The user-level content to evaluate.
            model_override: Optional model name to override the default.

        Returns:
            A parsed JSON dict from the model response.
            On failure, returns {"error": "description"}.
        """
        pass

    @staticmethod
    def _clean_json_response(content: str) -> str:
        """Strip markdown code fences from model responses."""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    @staticmethod
    def _truncate(text: str, max_chars: int = 300000) -> str:
        """Truncate extremely large text payloads to prevent token overflow."""
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return text[:half] + "\n\n... [CONTENT TRUNCATED FOR TOKEN SAFETY] ...\n\n" + text[-half:]
