import json
from typing import Dict, Any, List
from .llm_client import generate_json_response
from .scoring import calculate_score
from .rubric_loader import (
    build_section_prompt,
    get_section_mapping,
    load_rubric,
)


def split_thesis_sections(text: str) -> Dict[str, str]:
    """
    Uses the centralized LLM client to split the extracted thesis text into strict sections.
    """
    system_prompt = """
    You are an academic document parser. Your task is to take the raw text of a university thesis or final year project and split it into its core sections.

    Rules:
    1. The document formatting may be messy. Look for logical transitions (e.g., "CHAPTER ONE", "INTRODUCTION", "REFERENCES").
    2. Extract the full text for each section.
    3. Do not summarize or alter the text. Just extract it.
    4. If a section is completely missing from the text, return an empty string "" for that field. Do not hallucinate content.
    5. Return ONLY a valid JSON object matching this exact schema:

    {
      "abstract": "...",
      "chapter1": "...",
      "chapter2": "...",
      "chapter3": "...",
      "chapter4": "...",
      "chapter5": "...",
      "references": "..."
    }
    """

    user_prompt = f"Raw Thesis Text:\n{text}"
    result = generate_json_response(system_prompt, user_prompt)
    
    required_keys = ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]
    for key in required_keys:
        if key not in result or result[key] is None:
            result[key] = ""
            
    return result


# ──────────────────────────────────────────────────────────────
# Shared system prompt template (section-specific rubric injected)
# ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """
You are a calm, experienced, and professional university supervisor grading an NMCN (Nursing and Midwifery Council of Nigeria) research project.
Your ONLY job is to identify specific issues, missing elements, or flaws in the provided section.
Do NOT calculate final scores. Only identify deductions.

{rubric_criteria}

CRITICAL TONE INSTRUCTIONS:
- Maintain academic professionalism. Be supportive, direct, and practical.
- Focus strictly on correction and guidance, not blame.
- DO NOT use emotional, dramatic, or colloquial phrases.
- Use simple, direct English with short, readable sentences.

CONFIDENCE & CERTAINTY RULE:
- Use cautious wording for subjective issues ("appears to", "may need", "could be improved").
- Use absolute certainty only for objective issues (missing content, wrong formatting, rubric violations).

EVIDENCE & QUOTATION RULE:
- NEVER hallucinate evidence. Only quote text that actually exists in the provided content.
- Keep quotes short and relevant.

RUBRIC-AWARE EVALUATION RULE:
- Every deduction MUST reference a specific criterion from the rubric above.
- Explain WHY marks were deducted by citing the rubric expectation.
- The `rubric.section` must be "{section_name}".
- The `rubric.max_marks` must be {max_marks}.
- The `rubric.expected_requirement` must describe the specific criterion being violated.

Provide your output STRICTLY as a JSON object matching this schema:
{{
  "issues": [
    {{
      "issue_title": "Short descriptive title",
      "severity": "low | medium | high",
      "rubric": {{
        "section": "{section_name}",
        "max_marks": {max_marks},
        "expected_requirement": "Criterion name - X marks"
      }},
      "evidence": {{
        "quote": "Exact text from the student's work...",
        "location": "{section_name}"
      }},
      "deduction_reasoning": "Why this violates the rubric requirement...",
      "supervisor_note": "Professional guidance for the student...",
      "suggested_fix": "Specific action the student should take...",
      "recoverable_marks": 1
    }}
  ]
}}
"""


def _evaluate_section(section_name: str, section_text: str, institution: str = "nmcn") -> List[Dict]:
    """
    Evaluates a SINGLE thesis section against only its relevant rubric criteria.
    Returns a list of issues found in that section.
    """
    if not section_text or section_text.strip() == "" or section_text.strip() == "Not provided.":
        return []
    
    rubric_criteria = build_section_prompt(section_name, institution)
    rubric_data = load_rubric(institution)
    section_data = rubric_data["sections"].get(section_name, {})
    max_marks = section_data.get("total", 0)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        rubric_criteria=rubric_criteria,
        section_name=section_name,
        max_marks=max_marks,
    )
    
    # Truncate section text to a safe limit
    max_chars = 15000 if "Chapter" in section_name else 5000
    user_prompt = f"Evaluate this section of the NMCN research project:\n\n{section_name}:\n{section_text[:max_chars]}"
    
    ai_result = generate_json_response(system_prompt, user_prompt)
    
    if "error" in ai_result:
        print(f"Warning: AI evaluation failed for {section_name}: {ai_result['error']}")
        return []
    
    return ai_result.get("issues", [])


def evaluate_thesis(text: str, institution: str = "nmcn") -> Dict[str, Any]:
    """
    Evaluates the thesis section-by-section.
    Each section only receives its own rubric criteria — no wasted tokens.
    """
    # 1. Extract sections
    sections = split_thesis_sections(text)
    
    if "error" in sections:
        return sections

    # 2. Get section mapping (thesis_key -> rubric section name)
    section_map = get_section_mapping(institution)
    
    # 3. Evaluate each section independently with only its rubric
    all_issues = []
    for thesis_key, rubric_section in section_map.items():
        section_text = sections.get(thesis_key, "")
        if section_text:
            print(f"  -> Evaluating: {rubric_section}...")
            issues = _evaluate_section(rubric_section, section_text, institution)
            all_issues.extend(issues)
    
    # 4. Cross-Section Validation
    from .validation_engine import run_cross_validation
    print("  -> Running Cross-Section Validation...")
    cross_validation_result = run_cross_validation(sections)
    
    # 5. Deterministic Python Scoring
    scoring_result = calculate_score(all_issues, institution)
    
    # Apply cross-validation deductions
    scoring_result["overall_score"] -= cross_validation_result["total_deductions"]
    scoring_result["cross_validation"] = cross_validation_result
    
    # Attach sections for UI
    scoring_result["sections"] = sections
    scoring_result["institution"] = institution
    return scoring_result
