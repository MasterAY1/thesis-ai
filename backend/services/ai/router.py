"""
AI Router — Intelligent task routing between Gemini (fast/cheap) and GitHub GPT (reasoning).

Routing Logic:
    1. Gemini handles: section splitting, quick grading, formatting, rubric evaluation
    2. GitHub GPT handles: contradiction analysis, cross-section validation, advanced feedback
    3. If Gemini fails (error, rate-limit, bad JSON), automatically falls back to GitHub GPT
    4. Every call is logged with provider, latency, and retry metadata
"""
import os
import time
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .providers.gemini_provider import GeminiProvider
from .providers.github_provider import GitHubProvider

logger = logging.getLogger("thesis_ai.router")

# ──────────────────────────────────────────────────────────────
# Task classification — which provider handles which task
# ──────────────────────────────────────────────────────────────

GEMINI_TASKS = {
    "extract_sections",
    "quick_score",
    "citation_scan",
    "formatting_checks",
    "rubric_matching",
    "section_evaluation",
}

GITHUB_TASKS = {
    "contradiction_analysis",
    "methodology_validation",
    "cross_section_consistency",
    "advanced_feedback_generation",
    "academic_tone_review",
    "final_supervisor_notes",
}

# Tasks that should ALWAYS try GitHub first (complex reasoning)
PREMIUM_TASKS = GITHUB_TASKS


class AIRouter:
    """
    Intelligent AI router that selects the optimal provider per task.

    Default flow:
        1. Check if task is a premium reasoning task -> use GitHub GPT
        2. Otherwise -> use Gemini
        3. If primary provider fails -> fallback to the other provider
    """

    def __init__(self):
        load_dotenv()
        self._gemini = None
        self._github = None
        self.primary = os.getenv("PRIMARY_MODEL", "gemini")
        self.fallback = os.getenv("FALLBACK_MODEL", "github")

    @property
    def gemini(self) -> GeminiProvider:
        if self._gemini is None:
            self._gemini = GeminiProvider()
        return self._gemini

    @property
    def github(self) -> GitHubProvider:
        if self._github is None:
            self._github = GitHubProvider()
        return self._github

    def _get_provider(self, name: str):
        """Resolve a provider by name string."""
        if name == "gemini":
            return self.gemini
        elif name == "github":
            return self.github
        else:
            logger.warning(f"Unknown provider '{name}', defaulting to gemini")
            return self.gemini

    def _select_provider(self, task: str) -> tuple:
        """
        Select primary and fallback provider based on task type.
        Returns: (primary_provider, fallback_provider, reason)
        """
        if task in PREMIUM_TASKS:
            # Complex reasoning -> try GitHub first, Gemini fallback
            return self.github, self.gemini, "premium_task"

        # Everything else -> Gemini first, GitHub fallback
        return self.gemini, self.github, "standard_task"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "general",
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route an AI generation request to the optimal provider.

        Args:
            system_prompt: System-level instruction.
            user_prompt: User-level content to evaluate.
            task: Task identifier for routing decisions.
            model_override: Force a specific model name (bypasses routing).

        Returns:
            Parsed JSON response with metadata about which provider handled it.
        """
        primary, fallback, reason = self._select_provider(task)

        # --- Attempt primary provider ---
        start = time.time()
        logger.info(f"[{task}] Routing to {primary.name} (reason: {reason})")

        result = primary.generate(system_prompt, user_prompt, model_override)
        latency = round(time.time() - start, 2)

        if "error" not in result:
            logger.info(f"[{task}] {primary.name} succeeded in {latency}s")
            result["_meta"] = {
                "provider": primary.name,
                "task": task,
                "latency_s": latency,
                "fallback_used": False,
            }
            return result

        # --- Primary failed, try fallback ---
        logger.warning(f"[{task}] {primary.name} failed ({result.get('error', 'unknown')}), falling back to {fallback.name}")

        start = time.time()
        fallback_result = fallback.generate(system_prompt, user_prompt, model_override)
        fallback_latency = round(time.time() - start, 2)

        if "error" not in fallback_result:
            logger.info(f"[{task}] Fallback {fallback.name} succeeded in {fallback_latency}s")
            fallback_result["_meta"] = {
                "provider": fallback.name,
                "task": task,
                "latency_s": fallback_latency,
                "fallback_used": True,
                "primary_error": result.get("error", ""),
            }
            return fallback_result

        # --- Both providers failed ---
        logger.error(f"[{task}] Both providers failed. Primary: {result.get('error')}, Fallback: {fallback_result.get('error')}")
        return {
            "error": f"All AI providers failed for task '{task}'. Primary ({primary.name}): {result.get('error')}. Fallback ({fallback.name}): {fallback_result.get('error')}.",
            "_meta": {
                "provider": "none",
                "task": task,
                "fallback_used": True,
            },
        }


# ──────────────────────────────────────────────────────────────
# Module-level singleton — import and use this directly
# ──────────────────────────────────────────────────────────────
_router_instance = None


def get_router() -> AIRouter:
    """Get or create the singleton AI router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = AIRouter()
    return _router_instance
