"""
Cross-Section Validation Engine — Deep Mode Only.

Runs AFTER individual section evaluations to detect inconsistencies
between chapters that only emerge when comparing content across sections.

Optimizations:
  - run_cross_validation_async(): all rules run in parallel via asyncio.gather().
  - Gated to Deep Mode only (caller is responsible for the gate).
  - Each rule's context is capped at 3000 chars to keep prompts fast.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List

from .ai.router import get_router
from .chunking import safe_truncate_for_github, estimate_tokens

logger = logging.getLogger("thesis_ai.validation")


# ── Validation rules ───────────────────────────────────────────────────────────

VALIDATION_RULES = [
    {
        "id": "obj_method_alignment",
        "rule": "Objectives <-> Methodology Alignment",
        "description": "Research objectives should align with the methodology used. Quantitative objectives need quantitative methods.",
        "sections_needed": ["chapter1", "chapter3"],
        "deduction": 3,
    },
    {
        "id": "rq_findings_alignment",
        "rule": "Research Questions <-> Findings Alignment",
        "description": "Every research question or hypothesis stated in Chapter 1 should have a corresponding finding in Chapter 4.",
        "sections_needed": ["chapter1", "chapter4"],
        "deduction": 3,
    },
    {
        "id": "method_results_alignment",
        "rule": "Methodology <-> Results Alignment",
        "description": "Statistical tests and analysis methods described in Chapter 3 should appear in the Chapter 4 results.",
        "sections_needed": ["chapter3", "chapter4"],
        "deduction": 2,
    },
    {
        "id": "findings_conclusion_alignment",
        "rule": "Findings <-> Conclusion Alignment",
        "description": "Conclusions in Chapter 5 should be directly supported by findings reported in Chapter 4.",
        "sections_needed": ["chapter4", "chapter5"],
        "deduction": 2,
    },
    {
        "id": "abstract_thesis_alignment",
        "rule": "Abstract <-> Thesis Content Alignment",
        "description": "The abstract should accurately summarize the actual methodology, findings, and conclusions from the thesis.",
        "sections_needed": ["abstract", "chapter3", "chapter4"],
        "deduction": 2,
    },
]


# ── Sync helper ────────────────────────────────────────────────────────────────

def _validate_rule(rule: Dict, sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Runs a single cross-section validation rule via AI with token-safe context.
    Synchronous — called from asyncio.to_thread().
    """
    t_start = time.monotonic()

    # Build context from relevant sections — cap each section to 3000 chars
    section_context = ""
    for key in rule["sections_needed"]:
        label = _section_label(key)
        text = sections.get(key, "")[:3000]
        section_context += f"\n{label}:\n{text}\n"

    section_context = safe_truncate_for_github(section_context)
    total_tokens = estimate_tokens(section_context)
    logger.info(f"Cross-validation '{rule['id']}': {len(section_context)} chars (~{total_tokens} tokens)")

    system_prompt = f"""
You are a calm, professional academic reviewer performing a cross-section consistency check on a research project.

VALIDATION RULE: {rule['rule']}
DESCRIPTION: {rule['description']}

Your task is to determine if the content across these sections is CONSISTENT.

IMPORTANT RULES:
- Only flag genuine inconsistencies, not minor stylistic differences.
- Use cautious wording when the evidence is ambiguous.
- NEVER hallucinate quotes. Only quote text that exists in the provided content.
- Be direct and professional.

Respond with STRICTLY this JSON schema:
{{
  "status": "pass" or "fail",
  "explanation": "Clear explanation of whether the sections are consistent or not.",
  "evidence": [
    {{
      "source_section": "Chapter One",
      "quote": "exact quote from the text..."
    }}
  ],
  "suggested_fix": "Specific action to resolve the inconsistency (null if pass)."
}}
"""

    user_prompt = f"Check cross-section consistency:\n{section_context}"

    router = get_router()
    ai_result = router.generate(
        system_prompt, user_prompt,
        task="cross_section_consistency",
        evaluation_mode="deep",  # cross-validation is always deep mode
    )

    meta = ai_result.pop("_meta", {})
    provider = meta.get("provider", "unknown")
    latency = meta.get("latency_s", "?")
    duration = round(time.monotonic() - t_start, 2)
    logger.info(f"[{provider}] {rule['rule']} validated in {latency}s (total={duration}s)")

    if "error" in ai_result:
        logger.warning(f"Cross-validation failed for '{rule['rule']}': {ai_result['error']}")
        return {
            "rule": rule["rule"],
            "status": "skipped",
            "deduction": 0,
            "explanation": "Validation could not be completed due to an API error.",
            "evidence": [],
            "suggested_fix": None,
        }

    status = ai_result.get("status", "pass")

    return {
        "rule": rule["rule"],
        "status": status,
        "deduction": rule["deduction"] if status == "fail" else 0,
        "explanation": ai_result.get("explanation", ""),
        "evidence": ai_result.get("evidence", []),
        "suggested_fix": ai_result.get("suggested_fix") if status == "fail" else None,
    }


# ── Async parallel runner ──────────────────────────────────────────────────────

async def run_cross_validation_async(sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Runs ALL cross-section validation rules in parallel.

    Each rule is executed in a thread pool to avoid blocking the event loop.
    One failed rule does not cancel others — partial results are collected.

    Returns:
        Structured validation report (same shape as original run_cross_validation).
    """
    tasks = []
    applicable_rules = []
    skipped_validations = []

    for rule in VALIDATION_RULES:
        needed = rule["sections_needed"]
        available = all(
            sections.get(key, "").strip() and sections.get(key, "").strip() != "Not provided."
            for key in needed
        )

        if not available:
            skipped_validations.append({
                "rule": rule["rule"],
                "status": "skipped",
                "deduction": 0,
                "explanation": "One or more required sections are missing from the uploaded document.",
                "evidence": [],
                "suggested_fix": None,
            })
            continue

        logger.info(f"Scheduling cross-validation: {rule['rule']}")
        tasks.append(asyncio.to_thread(_validate_rule, rule, sections))
        applicable_rules.append(rule)

    # Run all applicable rules in parallel
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        results = []

    validations = list(skipped_validations)
    total_deductions = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            rule = applicable_rules[i]
            logger.error(f"Cross-validation rule '{rule['rule']}' raised: {result}")
            validations.append({
                "rule": rule["rule"],
                "status": "skipped",
                "deduction": 0,
                "explanation": f"Validation error: {result}",
                "evidence": [],
                "suggested_fix": None,
            })
        else:
            validations.append(result)
            if result.get("status") == "fail":
                total_deductions += result.get("deduction", 0)

    passes = sum(1 for v in validations if v["status"] == "pass")
    fails  = sum(1 for v in validations if v["status"] == "fail")

    return {
        "validations": validations,
        "total_deductions": total_deductions,
        "summary": (
            f"{passes} checks passed, {fails} inconsistencies found"
            if fails > 0
            else f"All {passes} consistency checks passed"
        ),
    }


# ── Sync wrapper (backward compat) ─────────────────────────────────────────────

def run_cross_validation(sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Synchronous wrapper for backward compatibility.
    Callers in existing code can still use this.
    """
    return asyncio.run(run_cross_validation_async(sections))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _section_label(key: str) -> str:
    """Maps thesis keys to readable labels."""
    labels = {
        "abstract":   "ABSTRACT / PRELIMINARY PAGES",
        "chapter1":   "CHAPTER ONE — INTRODUCTION",
        "chapter2":   "CHAPTER TWO — LITERATURE REVIEW",
        "chapter3":   "CHAPTER THREE — METHODOLOGY",
        "chapter4":   "CHAPTER FOUR — RESULTS",
        "chapter5":   "CHAPTER FIVE — DISCUSSION",
        "references": "REFERENCES",
    }
    return labels.get(key, key.upper())
