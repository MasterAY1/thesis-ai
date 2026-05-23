"""
ThesisAI Evaluation Pipeline — Optimized Async Version.

Optimizations applied:
  1. PARALLEL SECTION EVALUATION: asyncio.gather() runs all sections concurrently.
  2. FAST / DEEP MODES: Fast skips cross-validation; Deep runs full pipeline.
  3. SKIP LOGIC: Missing/empty sections return instantly without AI calls.
  4. CONTEXT TRIMMING: Max 12k chars per section via extract_relevant_context().
  5. PERFORMANCE TIMING: Every stage is timed and returned in debug mode.
  6. PER-SECTION PROGRESS: Emits live status updates to the job store.
  7. PARTIAL RESULTS: One failed section does NOT crash the evaluation.
"""
import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .ai.router import get_router
from .scoring import calculate_score
from .chunking import chunk_text, merge_section_results, estimate_tokens
from .rubric_loader import (
    build_section_prompt,
    get_section_mapping,
    load_rubric,
)
from .document_classifier import detect_document_type
from .feedback_styles import get_style_tone_modifier
from .context_extractor import extract_relevant_context, MAX_SECTION_CHARS

logger = logging.getLogger("thesis_ai.evaluation")

# ── Constants ──────────────────────────────────────────────────────────────────

EVALUATION_MODES = {"fast", "deep"}

# ── System prompt template ─────────────────────────────────────────────────────

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


# ── Missing section helper ─────────────────────────────────────────────────────

def _missing_chapter_result(section_name: str, max_marks: int) -> List[Dict]:
    """
    Return a canned deduction for a completely missing section.
    No AI call needed — immediate, deterministic result.
    """
    return [
        {
            "issue_title": f"{section_name} — Section Completely Missing",
            "severity": "high",
            "rubric": {
                "section": section_name,
                "max_marks": max_marks,
                "expected_requirement": f"Complete {section_name} section — {max_marks} marks",
            },
            "evidence": {
                "quote": "",
                "location": section_name,
            },
            "deduction_reasoning": (
                f"The {section_name} section was not found in the uploaded document. "
                "All marks for this section are forfeited."
            ),
            "supervisor_note": (
                f"The {section_name} section is required by the NMCN rubric and must be present. "
                "Please ensure this section is included in your final submission."
            ),
            "suggested_fix": f"Add a complete {section_name} section following the NMCN guidelines.",
            "recoverable_marks": max_marks,
            "_missing_section": True,
        }
    ]


# ── Section extraction ─────────────────────────────────────────────────────────

def split_thesis_sections(text: str) -> Dict[str, str]:
    """
    Two-stage section extraction using document chunking.

    Stage 1: Split document into manageable chunks.
    Stage 2: Gemini processes each chunk to identify which sections it contains.
    Stage 3: Merge chunk results into complete sections.
    """
    logger.info(f"Starting section extraction: {len(text)} chars (~{estimate_tokens(text)} tokens)")

    chunks = chunk_text(text, chunk_size=12000, overlap=1000)
    logger.info(f"Document split into {len(chunks)} chunks")

    if len(chunks) <= 1:
        return _extract_sections_single(text)

    chunk_sections: Dict[str, str] = {}
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)")
        result = _extract_sections_single(chunk)

        for key in ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]:
            existing = chunk_sections.get(key, "")
            new_content = result.get(key, "")
            if new_content and new_content.strip():
                if new_content.strip() not in existing:
                    chunk_sections[key] = (existing + "\n\n" + new_content).strip()

    required_keys = ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]
    for key in required_keys:
        if key not in chunk_sections or not chunk_sections[key]:
            chunk_sections[key] = ""

    total_extracted = sum(len(v) for v in chunk_sections.values())
    logger.info(
        f"Section extraction complete: {total_extracted} chars across "
        f"{sum(1 for v in chunk_sections.values() if v)} sections"
    )
    return chunk_sections


def _extract_sections_single(text: str) -> Dict[str, str]:
    """
    Extract sections from a single chunk of text using Gemini.
    Core extraction call — used for both single-shot and chunked extraction.
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

    result.pop("_meta", None)

    required_keys = ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]
    for key in required_keys:
        if key not in result or result[key] is None:
            result[key] = ""

    return result


# ── Section confidence estimator ──────────────────────────────────────────────

def _estimate_section_confidence(section_text: str, section_name: str) -> float:
    """
    Heuristically estimates how confident the AI evaluation of this section is.
    Based on: text length, presence of section heading, content density.
    Returns: float 0.0 – 1.0
    """
    if not section_text or len(section_text.strip()) < 50:
        return 0.30

    confidence = 0.50

    word_count = len(section_text.split())
    if word_count > 500:
        confidence += 0.20
    elif word_count > 200:
        confidence += 0.10

    name_lower = section_name.lower()
    text_lower = section_text.lower()
    if any(kw in text_lower[:500] for kw in [name_lower, "chapter", "introduction", "methodology", "references", "abstract"]):
        confidence += 0.10

    unique_words = len(set(section_text.lower().split()))
    density = unique_words / max(word_count, 1)
    if density > 0.35:
        confidence += 0.10

    return min(round(confidence, 2), 0.97)


# ── Core async section evaluator ──────────────────────────────────────────────

async def _evaluate_section_async(
    section_name: str,
    section_text: str,
    max_marks: int,
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
    evaluation_mode: str = "fast",
    progress_callback: Optional[Callable] = None,
) -> List[Dict]:
    """
    Evaluates a SINGLE thesis section asynchronously.

    - Uses extract_relevant_context() to trim context to MAX_SECTION_CHARS.
    - Offloads blocking AI call to a thread pool via asyncio.to_thread().
    - Emits progress via progress_callback if provided.

    Returns: list of issue dicts.
    """
    t_start = time.monotonic()

    # ── Skip logic: no AI call for missing/empty sections ──────────────────────
    if not section_text or section_text.strip() in ("", "Not provided."):
        logger.info(f"[SKIP] {section_name}: empty section → missing deduction (no AI call)")
        if progress_callback:
            progress_callback(section_name, "missing")
        return _missing_chapter_result(section_name, max_marks)

    if progress_callback:
        progress_callback(section_name, "evaluating")

    # ── Context trimming ───────────────────────────────────────────────────────
    rubric_criteria = build_section_prompt(section_name, institution)
    trimmed_text = extract_relevant_context(section_text, rubric_criteria)

    tone_modifier = get_style_tone_modifier(feedback_style)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        rubric_criteria=rubric_criteria,
        section_name=section_name,
        max_marks=max_marks,
    ) + f"\n\nTONE INSTRUCTION: {tone_modifier}"

    # ── Chunking for very large sections (after trimming) ─────────────────────
    section_chunks = chunk_text(trimmed_text, chunk_size=6000, overlap=500)

    try:
        if len(section_chunks) <= 1:
            user_prompt = f"Evaluate this section of the NMCN research project:\n\n{section_name}:\n{trimmed_text}"
            router = get_router()

            # Offload blocking AI call to thread pool
            ai_result = await asyncio.to_thread(
                router.generate, system_prompt, user_prompt,
                "section_evaluation", evaluation_mode
            )

            if "error" in ai_result:
                logger.warning(f"AI evaluation failed for {section_name}: {ai_result['error']}")
                if progress_callback:
                    progress_callback(section_name, "error")
                return []

            meta = ai_result.pop("_meta", {})
            provider = meta.get("provider", "unknown")
            latency = meta.get("latency_s", "?")
            duration = round(time.monotonic() - t_start, 2)
            logger.info(f"[{provider}] {section_name} evaluated in {latency}s (total={duration}s)")

            if progress_callback:
                progress_callback(section_name, "completed")

            return ai_result.get("issues", [])

        else:
            # Multiple chunks — evaluate each in parallel and merge
            logger.info(f"{section_name}: {len(section_chunks)} chunks → parallel evaluation")
            router = get_router()

            async def eval_chunk(i: int, chunk: str) -> Dict:
                up = f"Evaluate this section of the NMCN research project (part {i + 1}/{len(section_chunks)}):\n\n{section_name}:\n{chunk}"
                return await asyncio.to_thread(
                    router.generate, system_prompt, up,
                    "section_evaluation", evaluation_mode
                )

            chunk_results = await asyncio.gather(
                *[eval_chunk(i, c) for i, c in enumerate(section_chunks)],
                return_exceptions=True,
            )

            valid_results = [
                r for r in chunk_results
                if not isinstance(r, Exception) and "error" not in r
            ]
            for r in valid_results:
                r.pop("_meta", None)

            merged = merge_section_results(valid_results)
            duration = round(time.monotonic() - t_start, 2)
            logger.info(
                f"[chunked] {section_name}: {len(merged.get('issues', []))} issues "
                f"from {len(section_chunks)} chunks in {duration}s"
            )

            if progress_callback:
                progress_callback(section_name, "completed")

            return merged.get("issues", [])

    except Exception as exc:
        logger.error(f"Unhandled error evaluating {section_name}: {exc}", exc_info=True)
        if progress_callback:
            progress_callback(section_name, "error")
        return []


# ── Main async evaluation entry point ─────────────────────────────────────────

async def evaluate_thesis_async(
    text: str,
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
    evaluation_mode: str = "fast",
    progress_store: Optional[Dict] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Optimized async evaluation pipeline.

    Modes:
        fast — Gemini Flash only, parallel sections, no cross-validation.
               Target: 30–90 seconds.
        deep — Full pipeline: parallel sections + parallel cross-validation.
               Target: 2–4 minutes.

    Args:
        text:            Extracted thesis text.
        institution:     Rubric institution code (default: "nmcn").
        feedback_style:  Tone modifier key.
        evaluation_mode: "fast" | "deep".
        progress_store:  Dict ref from job store for live updates.
        debug:           If True, include per-stage timings in response.

    Returns:
        Full evaluation result dict (same shape as before for backward compat).
    """
    if evaluation_mode not in EVALUATION_MODES:
        logger.warning(f"Unknown evaluation_mode '{evaluation_mode}', defaulting to 'fast'")
        evaluation_mode = "fast"

    timings: Dict[str, float] = {}
    pipeline_start = time.monotonic()

    logger.info(
        f"[{evaluation_mode.upper()}] Starting evaluation: "
        f"{len(text)} chars (~{estimate_tokens(text)} tokens)"
    )

    # ── Helper: update the job progress store ─────────────────────────────────
    def _update_progress(section_name: str, status: str) -> None:
        if progress_store is not None:
            if "section_progress" not in progress_store:
                progress_store["section_progress"] = {}
            progress_store["section_progress"][section_name] = status

            # Update the coarse-grained progress message too
            completed = sum(
                1 for s in progress_store["section_progress"].values()
                if s in ("completed", "missing", "skipped")
            )
            total = len(progress_store["section_progress"])
            progress_store["progress"] = (
                f"Evaluating sections… {completed}/{total} complete"
            )

    # ── 1. Detect document type ───────────────────────────────────────────────
    t0 = time.monotonic()
    if progress_store is not None:
        progress_store["progress"] = "Detecting document type…"

    doc_classification = await asyncio.to_thread(detect_document_type, text)
    doc_type   = doc_classification["document_type"]
    skip_keys  = doc_classification.get("skip_sections", [])
    adjusted_total = doc_classification.get("adjusted_total")
    timings["classification_s"] = round(time.monotonic() - t0, 2)
    logger.info(
        f"Document type: {doc_type} (confidence={doc_classification['confidence']:.2f}), "
        f"skip={skip_keys}, took {timings['classification_s']}s"
    )

    # ── 2. Extract sections ───────────────────────────────────────────────────
    t0 = time.monotonic()
    if progress_store is not None:
        progress_store["progress"] = "Extracting sections…"

    sections = await asyncio.to_thread(split_thesis_sections, text)
    timings["extraction_s"] = round(time.monotonic() - t0, 2)

    if "error" in sections:
        return sections

    # Emit early signals: which sections were detected
    detected = [k for k, v in sections.items() if v and v.strip()]
    if progress_store is not None:
        progress_store["progress"] = f"Sections detected: {', '.join(detected)}"
        progress_store["detected_sections"] = detected
    logger.info(f"Sections extracted in {timings['extraction_s']}s: {detected}")

    # ── 3. Build section task list ────────────────────────────────────────────
    section_map = get_section_mapping(institution)
    rubric_data = load_rubric(institution)

    # Pre-populate section_progress with all expected sections
    if progress_store is not None:
        progress_store["section_progress"] = {
            rubric_name: ("skipped" if thesis_key in skip_keys else "pending")
            for thesis_key, rubric_name in section_map.items()
        }

    # Build coroutines for each non-skipped section
    section_tasks = []
    section_order = []

    for thesis_key, rubric_section in section_map.items():
        if thesis_key in skip_keys:
            logger.info(f"Skipping: {rubric_section} (proposal mode)")
            continue

        max_marks = rubric_data["sections"].get(rubric_section, {}).get("total", 0)
        section_text = sections.get(thesis_key, "")

        coro = _evaluate_section_async(
            section_name=rubric_section,
            section_text=section_text,
            max_marks=max_marks,
            institution=institution,
            feedback_style=feedback_style,
            evaluation_mode=evaluation_mode,
            progress_callback=_update_progress,
        )
        section_tasks.append(coro)
        section_order.append(rubric_section)

    # ── 4. Run ALL section evaluations in parallel ────────────────────────────
    t0 = time.monotonic()
    if progress_store is not None:
        progress_store["progress"] = f"Running {len(section_tasks)} section evaluations in parallel…"

    logger.info(f"Launching {len(section_tasks)} section evaluations in parallel…")

    section_results = await asyncio.gather(*section_tasks, return_exceptions=True)

    timings["section_evaluation_s"] = round(time.monotonic() - t0, 2)
    logger.info(f"All section evaluations completed in {timings['section_evaluation_s']}s")

    # ── 5. Merge all issues & build confidences ───────────────────────────────
    all_issues: List[Dict] = []
    section_confidences: Dict[str, float] = {}

    for i, result in enumerate(section_results):
        rubric_section = section_order[i]
        thesis_key = [k for k, v in section_map.items() if v == rubric_section][0]
        section_text = sections.get(thesis_key, "")

        if isinstance(result, Exception):
            logger.error(f"Section '{rubric_section}' raised exception: {result}")
            continue

        issues: List[Dict] = result or []

        confidence = _estimate_section_confidence(section_text, rubric_section)
        section_confidences[rubric_section] = confidence

        for issue in issues:
            issue["confidence"] = confidence

        all_issues.extend(issues)

    # ── 6. Cross-Section Validation (DEEP MODE ONLY) ─────────────────────────
    cross_validation_result: Dict[str, Any] = {
        "validations": [],
        "total_deductions": 0,
        "summary": "Cross-section validation skipped (Fast Mode). Switch to Deep Mode for full consistency checks.",
    }

    if evaluation_mode == "deep":
        from .validation_engine import run_cross_validation_async
        t0 = time.monotonic()
        if progress_store is not None:
            progress_store["progress"] = "Running cross-section validation…"

        cross_validation_result = await run_cross_validation_async(sections)
        timings["cross_validation_s"] = round(time.monotonic() - t0, 2)
        logger.info(f"Cross-validation completed in {timings['cross_validation_s']}s")

    # ── 7. Deterministic Python scoring ──────────────────────────────────────
    t0 = time.monotonic()
    scoring_result = calculate_score(all_issues, institution)
    scoring_result["overall_score"] -= cross_validation_result["total_deductions"]
    scoring_result["cross_validation"] = cross_validation_result
    timings["scoring_s"] = round(time.monotonic() - t0, 3)

    if adjusted_total is not None:
        scoring_result["total_marks"] = adjusted_total
        if scoring_result["overall_score"] > adjusted_total:
            scoring_result["overall_score"] = adjusted_total

    # ── 8. Attach metadata ────────────────────────────────────────────────────
    timings["total_s"] = round(time.monotonic() - pipeline_start, 2)

    scoring_result["sections"]            = sections
    scoring_result["institution"]         = institution
    scoring_result["document_type"]       = doc_classification
    scoring_result["feedback_style"]      = feedback_style
    scoring_result["section_confidences"] = section_confidences
    scoring_result["skipped_sections"]    = skip_keys
    scoring_result["evaluation_mode"]     = evaluation_mode

    if debug:
        scoring_result["_timings"] = timings

    if progress_store is not None:
        progress_store["progress"] = "Evaluation complete."

    logger.info(
        f"[{evaluation_mode.upper()}] Evaluation complete in {timings['total_s']}s. "
        f"Score: {scoring_result.get('overall_score', 'N/A')}/{scoring_result.get('total_marks', 100)}"
    )
    return scoring_result


# ── Sync wrapper (backward compatibility) ─────────────────────────────────────

def evaluate_thesis(
    text: str,
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
    evaluation_mode: str = "fast",
    progress_store: Optional[Dict] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Synchronous wrapper around evaluate_thesis_async().

    Maintains full backward compatibility with existing callers.
    Runs the async pipeline in a new event loop.
    """
    return asyncio.run(
        evaluate_thesis_async(
            text=text,
            institution=institution,
            feedback_style=feedback_style,
            evaluation_mode=evaluation_mode,
            progress_store=progress_store,
            debug=debug,
        )
    )
