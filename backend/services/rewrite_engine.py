"""
AI Rewrite Engine — "Fix This For Me"
Generates academic rewrites for specific deduction issues.

The AI receives:
- The specific issue title and description
- The feedback style (tone modifier)
- The section name and brief context
- Returns a direct academic rewrite + improvement tips
"""
import logging
from typing import Dict, Any
from .ai.router import get_router
from .feedback_styles import get_style_prompt

logger = logging.getLogger("thesis_ai.rewrite")

# Max chars of context to include — keeps tokens very low
MAX_CONTEXT_CHARS = 1500


def rewrite_issue(
    issue_title: str,
    issue_description: str,
    section_name: str,
    context: str = "",
    feedback_style: str = "friendly_lecturer",
    institution_name: str = "NMCN",
) -> Dict[str, Any]:
    """
    Generates an AI rewrite for a specific grading deduction.

    Args:
        issue_title:       Short title of the issue (e.g. "Sampling technique unclear")
        issue_description: Full explanation from the evaluation (deduction_reasoning + suggested_fix)
        section_name:      e.g. "Chapter Three", "Preliminary Pages"
        context:           A short excerpt from the student's original text (optional)
        feedback_style:    One of: strict_supervisor, friendly_lecturer, blunt_examiner,
                           student_helper, quick_summary
        institution_name:  The name of the institution/council (e.g., Lagos State University, NMCN)

    Returns:
        {
            "rewrite": "A convenience sampling technique was adopted...",
            "tips": ["Ensure you describe inclusion criteria...", ...]
        }
    """
    style_instruction = get_style_prompt(feedback_style)
    truncated_context = context[:MAX_CONTEXT_CHARS] if context else "Not provided."

    system_prompt = f"""
You are a specialist academic writing assistant helping a Nigerian student improve their {institution_name} research project.

{style_instruction}

YOUR TASK:
Produce a corrected academic rewrite for ONE specific issue identified in their thesis.

STRICT RULES:
1. Write ONLY the corrected passage — no preamble, no meta-commentary.
2. Maintain formal academic style appropriate for a {institution_name} project.
3. The rewrite must be directly usable — paste-ready into the thesis.
4. Maximum 200 words for the rewrite.
5. Also provide 2-3 short improvement tips as bullet points.
6. Return ONLY valid JSON matching this schema exactly:

{{
  "rewrite": "The corrected academic text here...",
  "tips": [
    "Tip 1...",
    "Tip 2...",
    "Tip 3..."
  ]
}}
"""

    user_prompt = f"""
Section: {section_name}

Issue Identified: {issue_title}

Problem Description: {issue_description}

Student's Original Text (for context):
\"\"\"{truncated_context}\"\"\"

Generate a corrected academic rewrite for this specific issue.
"""

    router = get_router()
    result = router.generate(system_prompt, user_prompt, task="section_evaluation")
    result.pop("_meta", None)

    # Validate response shape
    if "error" in result:
        logger.warning(f"Rewrite failed for '{issue_title}': {result['error']}")
        return {
            "rewrite": "Unable to generate rewrite at this time. Please try again.",
            "tips": ["Review the supervisor note for guidance.", "Consult the rubric criteria for this section."],
        }

    return {
        "rewrite": result.get("rewrite", ""),
        "tips": result.get("tips", []),
    }
