"""
Cross-Section Validation Engine
Runs AFTER individual section evaluations to detect inconsistencies
between chapters that only emerge when comparing content across sections.

Token Safety: Each cross-validation call is truncated to fit within
GitHub GPT's limits before being sent.
"""
import logging
from typing import Dict, Any, List
from .ai.router import get_router
from .chunking import safe_truncate_for_github, estimate_tokens

logger = logging.getLogger("thesis_ai.validation")


# ──────────────────────────────────────────────────────────────
# Validation Rules — each rule compares two or more sections
# ──────────────────────────────────────────────────────────────

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


def run_cross_validation(sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Runs all cross-section validation rules against the extracted thesis sections.
    Each rule compares content from two or more chapters using the AI.
    Returns a structured validation report.
    """
    validations = []
    total_deductions = 0
    
    for rule in VALIDATION_RULES:
        # Check if all needed sections have content
        needed = rule["sections_needed"]
        available = all(
            sections.get(key, "").strip() and sections.get(key, "").strip() != "Not provided."
            for key in needed
        )
        
        if not available:
            # Skip rules where required sections are missing
            validations.append({
                "rule": rule["rule"],
                "status": "skipped",
                "deduction": 0,
                "explanation": "One or more required sections are missing from the uploaded document.",
                "evidence": [],
                "suggested_fix": None,
            })
            continue
        
        print(f"  -> Cross-validating: {rule['rule']}...")
        result = _validate_rule(rule, sections)
        
        if result["status"] == "fail":
            total_deductions += result["deduction"]
        
        validations.append(result)
    
    passes = sum(1 for v in validations if v["status"] == "pass")
    fails = sum(1 for v in validations if v["status"] == "fail")
    
    return {
        "validations": validations,
        "total_deductions": total_deductions,
        "summary": f"{passes} checks passed, {fails} inconsistencies found" if fails > 0
                   else f"All {passes} consistency checks passed",
    }


def _validate_rule(rule: Dict, sections: Dict[str, str]) -> Dict[str, Any]:
    """Runs a single cross-section validation rule via AI with token-safe context."""
    
    # Build context from relevant sections — cap each section to 3000 chars
    # This keeps combined context well within GitHub GPT limits
    section_context = ""
    for key in rule["sections_needed"]:
        label = _section_label(key)
        text = sections.get(key, "")[:3000]
        section_context += f"\n{label}:\n{text}\n"
    
    # Apply token safety to the full combined context
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
    }},
    {{
      "source_section": "Chapter Three",
      "quote": "exact quote from the text..."
    }}
  ],
  "suggested_fix": "Specific action to resolve the inconsistency (null if pass)."
}}
"""

    user_prompt = f"Check cross-section consistency:\n{section_context}"
    
    router = get_router()
    ai_result = router.generate(system_prompt, user_prompt, task="cross_section_consistency")
    
    # Log which provider handled the validation
    meta = ai_result.pop("_meta", {})
    provider = meta.get("provider", "unknown")
    latency = meta.get("latency_s", "?")
    print(f"    [{provider}] {rule['rule']} validated in {latency}s")
    
    if "error" in ai_result:
        print(f"  Warning: Cross-validation failed for '{rule['rule']}': {ai_result['error']}")
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


def _section_label(key: str) -> str:
    """Maps thesis keys to readable labels."""
    labels = {
        "abstract": "ABSTRACT / PRELIMINARY PAGES",
        "chapter1": "CHAPTER ONE — INTRODUCTION",
        "chapter2": "CHAPTER TWO — LITERATURE REVIEW",
        "chapter3": "CHAPTER THREE — METHODOLOGY",
        "chapter4": "CHAPTER FOUR — RESULTS",
        "chapter5": "CHAPTER FIVE — DISCUSSION",
        "references": "REFERENCES",
    }
    return labels.get(key, key.upper())
