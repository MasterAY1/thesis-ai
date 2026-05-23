"""
AI Router — Intelligent task routing between Gemini (fast/cheap) and GitHub GPT (reasoning).

Routing Logic:
    FAST MODE:  All tasks → Gemini Flash. No GitHub GPT used at all.
    DEEP MODE:
        1. Premium tasks (contradiction, cross-validation) → GitHub GPT first.
        2. Standard tasks → Gemini first, GitHub fallback.
        3. If primary fails → fallback to the other provider.

Every call is logged with provider, latency, evaluation_mode, and task.
"""
import os
import time
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .providers.gemini_provider import GeminiProvider
from .providers.github_provider import GitHubProvider

logger = logging.getLogger("thesis_ai.router")

# ── Task classification ────────────────────────────────────────────────────────

# Tasks always handled by Gemini (fast, cheap, bulk)
GEMINI_TASKS = {
    "extract_sections",
    "quick_score",
    "citation_scan",
    "formatting_checks",
    "rubric_matching",
    "section_evaluation",
    "structural_analysis",
}

# Tasks that must NEVER fall back to GitHub GPT (payload too large)
GEMINI_ONLY_TASKS = {
    "extract_sections",
}

# Tasks that use GitHub GPT in Deep Mode (complex reasoning)
DEEP_MODE_PREMIUM_TASKS = {
    "contradiction_analysis",
    "methodology_validation",
    "cross_section_consistency",
    "advanced_feedback_generation",
    "academic_tone_review",
    "final_supervisor_notes",
}


class AIRouter:
    """
    Mode-aware AI router.

    Fast Mode: All tasks → Gemini Flash. Maximum speed.
    Deep Mode: Premium tasks → GitHub GPT; standard tasks → Gemini.
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

    def _select_provider(self, task: str, evaluation_mode: str) -> tuple:
        """
        Select primary and fallback provider based on task type and evaluation mode.

        Fast Mode: Always Gemini, no fallback to GitHub (speed priority).
        Deep Mode: Premium tasks → GitHub first; standard → Gemini first.

        Returns: (primary_provider, fallback_provider, reason)
        """
        if evaluation_mode == "fast":
            # Fast mode: Gemini Flash for everything, no GitHub
            return self.gemini, None, "fast_mode_gemini_only"

        # Deep mode: respect task classifications
        if task in DEEP_MODE_PREMIUM_TASKS:
            return self.github, self.gemini, "deep_mode_premium_task"

        return self.gemini, self.github, "deep_mode_standard_task"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "general",
        evaluation_mode: str = "fast",
        model_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route an AI generation request to the optimal provider.

        Args:
            system_prompt:    System-level instruction.
            user_prompt:      User-level content to evaluate.
            task:             Task identifier for routing decisions.
            evaluation_mode:  "fast" | "deep" — controls provider selection.
            model_override:   Force a specific model name (bypasses routing).

        Returns:
            Parsed JSON response with metadata about which provider handled it.
        """
        primary, fallback, reason = self._select_provider(task, evaluation_mode)

        # ── Attempt primary provider ──────────────────────────────────────────
        start = time.time()
        logger.info(
            f"[{evaluation_mode.upper()}][{task}] Routing to {primary.name} "
            f"(reason: {reason})"
        )

        result = primary.generate(system_prompt, user_prompt, model_override)
        latency = round(time.time() - start, 2)

        if "error" not in result:
            logger.info(f"[{task}] {primary.name} succeeded in {latency}s")
            result["_meta"] = {
                "provider": primary.name,
                "task": task,
                "latency_s": latency,
                "fallback_used": False,
                "evaluation_mode": evaluation_mode,
            }
            return result

        # ── Primary failed ────────────────────────────────────────────────────

        # Fast mode or Gemini-only tasks: no fallback
        if evaluation_mode == "fast" or task in GEMINI_ONLY_TASKS:
            logger.error(
                f"[{task}] {primary.name} failed. No fallback in {evaluation_mode} mode. "
                f"Error: {result.get('error')}"
            )
            result["_meta"] = {
                "provider": "none",
                "task": task,
                "fallback_used": False,
                "reason": f"{evaluation_mode}_mode_no_fallback",
                "evaluation_mode": evaluation_mode,
            }
            return result

        # Deep mode: try fallback
        if fallback is None:
            logger.error(f"[{task}] No fallback provider configured.")
            result["_meta"] = {"provider": "none", "task": task, "fallback_used": False}
            return result

        logger.warning(
            f"[{task}] {primary.name} failed ({result.get('error', 'unknown')}), "
            f"falling back to {fallback.name}"
        )

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
                "evaluation_mode": evaluation_mode,
            }
            return fallback_result

        # ── Both providers failed ─────────────────────────────────────────────
        logger.error(
            f"[{task}] Both providers failed. "
            f"Primary ({primary.name}): {result.get('error')}. "
            f"Fallback ({fallback.name}): {fallback_result.get('error')}."
        )
        return {
            "error": (
                f"All AI providers failed for task '{task}'. "
                f"Primary ({primary.name}): {result.get('error')}. "
                f"Fallback ({fallback.name}): {fallback_result.get('error')}."
            ),
            "_meta": {
                "provider": "none",
                "task": task,
                "fallback_used": True,
                "evaluation_mode": evaluation_mode,
            },
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
_router_instance = None


def get_router() -> AIRouter:
    """Get or create the singleton AI router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = AIRouter()
    return _router_instance
