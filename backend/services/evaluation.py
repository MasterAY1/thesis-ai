"""
ThesisAI Evaluation Pipeline — Two-stage extraction with chunking.
Phase 2: Integrates document classifier, feedback styles, confidence scoring,
         proposal-aware section skipping.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from .ai.router import get_router
from .scoring import calculate_score
from .chunking import chunk_text, merge_section_results, estimate_tokens, safe_truncate_for_github
from .rubric_loader import (
    build_section_prompt,
    get_section_mapping,
    load_rubric,
)
from .document_classifier import detect_document_type
from .feedback_styles import get_style_tone_modifier

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


def _evaluate_section(
    section_name: str,
    section_text: str,
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
) -> List[Dict]:
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

    tone_modifier = get_style_tone_modifier(feedback_style)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        rubric_criteria=rubric_criteria,
        section_name=section_name,
        max_marks=max_marks,
    ) + f"\n\nTONE INSTRUCTION: {tone_modifier}"

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


def evaluate_thesis(
    text: str,
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
) -> Dict[str, Any]:
    """
    Phase 2 evaluation pipeline:
      - Detects document type (proposal / thesis / seminar / dissertation)
      - Skips non-applicable sections for proposals
      - Applies feedback style tone to all AI calls
      - Attaches confidence metadata to every section result
    """
    logger.info(f"Starting thesis evaluation: {len(text)} chars (~{estimate_tokens(text)} tokens)")

    # 1. Detect document type FIRST — determines which sections to grade
    print("  -> Detecting document type...")
    doc_classification = detect_document_type(text)
    doc_type    = doc_classification["document_type"]
    skip_keys   = doc_classification.get("skip_sections", [])
    adjusted_total = doc_classification.get("adjusted_total")
    logger.info(f"Document type: {doc_type} (confidence={doc_classification['confidence']:.2f}), skip={skip_keys}")
    print(f"  -> Document type: {doc_type.upper()} (confidence={doc_classification['confidence']:.0%})")

    # 2. Extract sections
    print("  -> Extracting sections...")
    sections = split_thesis_sections(text)

    if "error" in sections:
        return sections

    # 3. Get section mapping (thesis_key -> rubric section name)
    section_map = get_section_mapping(institution)

    # 4. Evaluate each non-skipped section
    all_issues = []
    section_confidences: Dict[str, float] = {}

    for thesis_key, rubric_section in section_map.items():
        # Skip sections not applicable for this document type
        if thesis_key in skip_keys:
            print(f"  -> Skipping: {rubric_section} (proposal mode)")
            continue

        section_text = sections.get(thesis_key, "")
        if section_text:
            print(f"  -> Evaluating: {rubric_section}...")
            issues = _evaluate_section(rubric_section, section_text, institution, feedback_style)

            # Compute per-section confidence from text quality signals
            confidence = _estimate_section_confidence(section_text, rubric_section)
            section_confidences[rubric_section] = confidence

            # Attach confidence to each issue for downstream UI
            for issue in issues:
                issue["confidence"] = confidence

            all_issues.extend(issues)

    # 5. Cross-Section Validation
    from .validation_engine import run_cross_validation
    print("  -> Running Cross-Section Validation...")
    cross_validation_result = run_cross_validation(sections)

    # 6. Deterministic Python Scoring
    scoring_result = calculate_score(all_issues, institution)

    # 7. Apply cross-validation deductions
    scoring_result["overall_score"] -= cross_validation_result["total_deductions"]
    scoring_result["cross_validation"] = cross_validation_result

    # 8. If proposal, cap total_marks to adjusted total
    if adjusted_total is not None:
        scoring_result["total_marks"] = adjusted_total
        # Re-clamp overall score
        if scoring_result["overall_score"] > adjusted_total:
            scoring_result["overall_score"] = adjusted_total

    # 9. Attach Phase 2 metadata
    scoring_result["sections"]             = sections
    scoring_result["institution"]          = institution
    scoring_result["document_type"]        = doc_classification
    scoring_result["feedback_style"]       = feedback_style
    scoring_result["section_confidences"]  = section_confidences
    scoring_result["skipped_sections"]     = skip_keys

    logger.info(f"Evaluation complete. Score: {scoring_result.get('overall_score', 'N/A')}/{scoring_result.get('total_marks', 100)}")
    return scoring_result


def _estimate_section_confidence(section_text: str, section_name: str) -> float:
    """
    Heuristically estimates how confident the AI evaluation of this section is.
    Based on: text length, presence of section heading, content density.

    Returns: float 0.0 – 1.0
    """
    if not section_text or len(section_text.strip()) < 50:
        return 0.30  # Very short — low confidence

    confidence = 0.50  # Base

    # Length bonus (more text = more to evaluate)
    word_count = len(section_text.split())
    if word_count > 500:
        confidence += 0.20
    elif word_count > 200:
        confidence += 0.10

    # Heading presence
    name_lower = section_name.lower()
    text_lower = section_text.lower()
    if any(kw in text_lower[:500] for kw in [name_lower, "chapter", "introduction", "methodology", "references", "abstract"]):
        confidence += 0.10

    # Content density — penalise if mostly whitespace or repetition
    unique_words = len(set(section_text.lower().split()))
    density = unique_words / max(word_count, 1)
    if density > 0.35:
        confidence += 0.10

    return min(round(confidence, 2), 0.97)
