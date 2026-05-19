"""
ThesisAI Evaluation Pipeline — Two-stage extraction with chunking.

Stage 1: Gemini performs lightweight section detection on document chunks.
Stage 2: Individual sections are sent to providers for rubric grading.
Cross-validation uses token-safe truncated context.

NEVER sends the entire thesis to GitHub GPT.
"""
import json
import logging
from typing import Dict, Any, List
from .ai.router import get_router
from .scoring import calculate_score
from .chunking import chunk_text, merge_section_results, estimate_tokens, safe_truncate_for_github
from .rubric_loader import (
    build_section_prompt,
    get_section_mapping,
    load_rubric,
)

logger = logging.getLogger("thesis_ai.evaluation")


def split_thesis_sections(text: str) -> Dict[str, str]:
    """
    Two-stage section extraction using document chunking.

    Stage 1: Split document into manageable chunks.
    Stage 2: Gemini processes each chunk to identify which sections it contains.
    Stage 3: Merge chunk results into complete sections.

    This prevents sending the entire thesis in a single API call.
    """
    logger.info(f"Starting section extraction: {len(text)} chars (~{estimate_tokens(text)} tokens)")

    # Stage 1: Chunk the document
    chunks = chunk_text(text, chunk_size=12000, overlap=1000)
    logger.info(f"Document split into {len(chunks)} chunks")

    if len(chunks) <= 1:
        # Small document — process in one shot (Gemini handles this fine)
        return _extract_sections_single(text)

    # Stage 2: Process each chunk with Gemini
    chunk_sections = {}
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)")
        result = _extract_sections_single(chunk)

        # Merge this chunk's results into the accumulated sections
        for key in ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]:
            existing = chunk_sections.get(key, "")
            new_content = result.get(key, "")
            if new_content and new_content.strip():
                # Append new content, avoiding duplication
                if new_content.strip() not in existing:
                    chunk_sections[key] = (existing + "\n\n" + new_content).strip()

    # Ensure all required keys exist
    required_keys = ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]
    for key in required_keys:
        if key not in chunk_sections or not chunk_sections[key]:
            chunk_sections[key] = ""

    total_extracted = sum(len(v) for v in chunk_sections.values())
    logger.info(f"Section extraction complete: {total_extracted} chars across {sum(1 for v in chunk_sections.values() if v)} sections")

    return chunk_sections


def _extract_sections_single(text: str) -> Dict[str, str]:
    """
    Extract sections from a single chunk of text using Gemini.
    This is the core extraction call — used for both single-shot and chunked extraction.
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

    router = get_router()
    result = router.generate(system_prompt, user_prompt, task="extract_sections")

    # Strip router metadata before returning to caller
    result.pop("_meta", None)

    required_keys = ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]
    for key in required_keys:
        if key not in result or result[key] is None:
            result[key] = ""

    return result


# ------------------------------------------------------------------
# Shared system prompt template (section-specific rubric injected)
# ------------------------------------------------------------------

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

    For large sections, uses chunking to split the section and merge results.
    Routed to Gemini (standard rubric evaluation task).
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

    # Truncate section text to a safe limit for the provider
    max_chars = 15000 if "Chapter" in section_name else 5000
    truncated_text = section_text[:max_chars]

    # If text is still very large, chunk it and merge results
    section_chunks = chunk_text(truncated_text, chunk_size=6000, overlap=500)

    if len(section_chunks) <= 1:
        # Single chunk — standard evaluation
        user_prompt = f"Evaluate this section of the NMCN research project:\n\n{section_name}:\n{truncated_text}"

        router = get_router()
        ai_result = router.generate(system_prompt, user_prompt, task="section_evaluation")

        if "error" in ai_result:
            logger.warning(f"AI evaluation failed for {section_name}: {ai_result['error']}")
            return []

        meta = ai_result.pop("_meta", {})
        provider = meta.get("provider", "unknown")
        latency = meta.get("latency_s", "?")
        logger.info(f"[{provider}] {section_name} evaluated in {latency}s")
        print(f"    [{provider}] {section_name} evaluated in {latency}s")

        return ai_result.get("issues", [])
    else:
        # Multiple chunks — evaluate each and merge
        logger.info(f"{section_name}: {len(section_chunks)} chunks for evaluation")
        chunk_results = []
        router = get_router()

        for i, chunk in enumerate(section_chunks):
            user_prompt = f"Evaluate this section of the NMCN research project (part {i + 1}/{len(section_chunks)}):\n\n{section_name}:\n{chunk}"
            ai_result = router.generate(system_prompt, user_prompt, task="section_evaluation")

            if "error" not in ai_result:
                meta = ai_result.pop("_meta", {})
                provider = meta.get("provider", "unknown")
                latency = meta.get("latency_s", "?")
                logger.info(f"[{provider}] {section_name} chunk {i + 1} in {latency}s")
                chunk_results.append(ai_result)

        merged = merge_section_results(chunk_results)
        print(f"    [chunked] {section_name}: {len(merged.get('issues', []))} issues from {len(section_chunks)} chunks")
        return merged.get("issues", [])


def evaluate_thesis(text: str, institution: str = "nmcn") -> Dict[str, Any]:
    """
    Evaluates the thesis section-by-section with chunking support.
    Each section only receives its own rubric criteria -- no wasted tokens.
    """
    logger.info(f"Starting thesis evaluation: {len(text)} chars (~{estimate_tokens(text)} tokens)")

    # 1. Extract sections (uses chunking for large documents)
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

    # 4. Cross-Section Validation (routed to GitHub GPT with token-safe context)
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

    logger.info(f"Evaluation complete. Score: {scoring_result.get('overall_score', 'N/A')}")
    return scoring_result
