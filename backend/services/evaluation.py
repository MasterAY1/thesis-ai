"""
ThesisAI Evaluation Pipeline — Deterministic Architecture v4

Architecture:
  1. DETERMINISTIC SECTION PARSER (regex) — replaces AI-based extraction
  2. RULE ENGINE (checklist) — catches objective issues BEFORE AI
  3. AI REASONING (Gemini, temp=0) — deeper analysis + explanations
  4. CONSISTENCY VERIFICATION — double-run guard for score stability
  5. DETERMINISTIC SCORING (Python math) — no AI in final score calc

Design principle: 70% deterministic, 30% AI reasoning.
Same document uploaded 10 times → nearly identical scores (±1 max).
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
from .section_parser import parse_thesis_sections, get_extraction_confidences, MIN_SECTION_CHARS
from .rule_engine import run_rule_checks

logger = logging.getLogger("thesis_ai.evaluation")

# ── Constants ──────────────────────────────────────────────────────────────────

EVALUATION_MODES = {"fast", "deep"}

# Minimum chars for a section to be sent to AI for evaluation.
# Below this → mark missing, score=0, NO AI call, NO hallucinated deductions.
MIN_SECTION_FOR_AI = {
    "abstract":   150,
    "chapter1":   800,
    "chapter2":   800,
    "chapter3":   800,
    "chapter4":   800,
    "chapter5":   800,
    "references": 300,
}

# ── System prompt template ─────────────────────────────────────────────────────
# Rewritten for SIMPLE, CLEAR, STUDENT-FRIENDLY language.
# No academic jargon. No robotic tone. Max 2-4 sentences per deduction.

SYSTEM_PROMPT_TEMPLATE = """
You are a helpful thesis reviewer checking a student's NMCN research project.
Your job is to find problems in this section and explain them simply.

{rubric_criteria}

IMPORTANT RULES:
- Write short, clear explanations. Use simple English.
- Maximum 2-4 sentences per issue.
- Do NOT use big grammar or academic jargon unless absolutely necessary.
- Explain issues the way a smart Nigerian lecturer would explain to a student.
- Be direct. Say what the problem is and how to fix it.
- Do NOT lecture the student. Just identify the issue and suggest the fix.

BAD examples (do NOT write like this):
- "The manuscript demonstrates insufficient methodological coherence."
- "The theoretical framework lacks conceptual integration."

GOOD examples (write like this):
- "Your methodology section does not clearly explain your research design."
- "You did not connect the theory to your study properly."

EVIDENCE RULES:
- NEVER make up quotes. Only quote text that actually exists in the content.
- If you cannot find a direct quote, leave the quote field empty.

SCORING RULES:
- Every issue MUST reference a specific rubric criterion.
- The `rubric.section` must be "{section_name}".
- The `rubric.max_marks` must be {max_marks}.
- Do NOT invent issues for content that does not exist.
- Do NOT grade missing subsections — the rule engine already handles those.
- Focus on QUALITY of existing content, not whether subsections exist.

Output STRICTLY as JSON:
{{
  "issues": [
    {{
      "issue_title": "Short clear title",
      "severity": "low | medium | high",
      "rubric": {{
        "section": "{section_name}",
        "max_marks": {max_marks},
        "expected_requirement": "Which criterion this violates"
      }},
      "evidence": {{
        "quote": "Exact text from the student's work (or empty if none)",
        "location": "{section_name}"
      }},
      "deduction_reasoning": "Why this is a problem (1-2 sentences).",
      "supervisor_note": "How to fix it (1-2 sentences).",
      "suggested_fix": "Specific action to take.",
      "recoverable_marks": 1
    }}
  ]
}}
"""


# ── Missing section result ─────────────────────────────────────────────────────

def _missing_chapter_result(section_name: str, max_marks: int) -> List[Dict]:
    """
    Return a canned deduction for a completely missing section.
    No AI call. Deterministic. Immediate.
    """
    return [
        {
            "issue_title": f"{section_name} — Not Found in Document",
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
                f"This section was not found in your uploaded document. "
                f"All {max_marks} marks for this section cannot be awarded."
            ),
            "supervisor_note": (
                f"Make sure your {section_name} section is included in your final submission."
            ),
            "suggested_fix": f"Add a complete {section_name} section following the NMCN guidelines.",
            "recoverable_marks": max_marks,
            "_missing_section": True,
            "_source": "missing_gate",
        }
    ]


# ── Core async section evaluator ──────────────────────────────────────────────

async def _evaluate_section_async(
    section_name: str,
    section_text: str,
    max_marks: int,
    thesis_key: str,
    institution: str = "nmcn",
    feedback_style: str = "friendly_lecturer",
    evaluation_mode: str = "fast",
    progress_callback: Optional[Callable] = None,
) -> List[Dict]:
    """
    Evaluates a SINGLE thesis section asynchronously.

    HARD GATE: If section text < MIN_SECTION_FOR_AI:
      → mark MISSING, score=0, NO AI call, NO hallucinated deductions.

    Otherwise:
      → Trim context, call AI (temp=0), return issues.
    """
    t_start = time.monotonic()

    # ── HARD GATE: missing/empty sections ──────────────────────────────────────
    min_chars = MIN_SECTION_FOR_AI.get(thesis_key, 800)
    section_stripped = (section_text or "").strip()

    if not section_stripped or len(section_stripped) < min_chars:
        logger.info(
            f"[GATE] {section_name}: {len(section_stripped)} chars < {min_chars} threshold → MISSING (no AI call)"
        )
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
    ) + f"\n\nTONE: {tone_modifier}"

    # ── Chunking for very large sections ──────────────────────────────────────
    section_chunks = chunk_text(trimmed_text, chunk_size=6000, overlap=500)

    try:
        if len(section_chunks) <= 1:
            user_prompt = f"Review this section of the student's thesis:\n\n{section_name}:\n{trimmed_text}"
            router = get_router()

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

            issues = ai_result.get("issues", [])
            # Tag all AI issues with source
            for issue in issues:
                issue["_source"] = "ai"
            return issues

        else:
            # Multiple chunks — evaluate each in parallel and merge
            logger.info(f"{section_name}: {len(section_chunks)} chunks → parallel evaluation")
            router = get_router()

            async def eval_chunk(i: int, chunk: str) -> Dict:
                up = f"Review this section of the student's thesis (part {i + 1}/{len(section_chunks)}):\n\n{section_name}:\n{chunk}"
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

            issues = merged.get("issues", [])
            for issue in issues:
                issue["_source"] = "ai"
            return issues

    except Exception as exc:
        logger.error(f"Unhandled error evaluating {section_name}: {exc}", exc_info=True)
        if progress_callback:
            progress_callback(section_name, "error")
        return []


# ── Consistency verification ──────────────────────────────────────────────────

async def _verify_consistency(
    sections: Dict[str, str],
    section_map: Dict[str, str],
    rubric_data: Dict,
    first_score: int,
    first_issues: List[Dict],
    institution: str,
    feedback_style: str,
    evaluation_mode: str,
    progress_callback: Optional[Callable],
) -> List[Dict]:
    """
    Double-run consistency check.
    If the score delta between two runs exceeds 3 marks,
    re-evaluate ONLY the inconsistent sections.

    Returns: final merged issue list.
    """
    # Run a second evaluation pass
    second_tasks = []
    second_order = []

    for thesis_key, rubric_section in section_map.items():
        section_text = sections.get(thesis_key, "")
        max_marks = rubric_data["sections"].get(rubric_section, {}).get("total", 0)

        # Only re-evaluate sections that had AI issues (rule-engine issues are stable)
        section_ai_issues = [i for i in first_issues if i.get("_source") == "ai" and
                             i.get("rubric", {}).get("section") == rubric_section]
        if not section_ai_issues:
            continue

        coro = _evaluate_section_async(
            section_name=rubric_section,
            section_text=section_text,
            max_marks=max_marks,
            thesis_key=thesis_key,
            institution=institution,
            feedback_style=feedback_style,
            evaluation_mode=evaluation_mode,
            progress_callback=None,  # silent second pass
        )
        second_tasks.append(coro)
        second_order.append(rubric_section)

    if not second_tasks:
        return first_issues

    logger.info(f"[CONSISTENCY] Running second pass on {len(second_tasks)} sections...")
    second_results = await asyncio.gather(*second_tasks, return_exceptions=True)

    # Build second issue list
    second_ai_issues: List[Dict] = []
    for i, result in enumerate(second_results):
        if isinstance(result, Exception):
            continue
        second_ai_issues.extend(result or [])

    # Calculate second score
    # Merge rule-engine issues (stable) + second AI issues
    rule_issues = [i for i in first_issues if i.get("_source") != "ai"]
    second_all = rule_issues + second_ai_issues
    second_scoring = calculate_score(second_all, institution)
    second_score = second_scoring.get("overall_score", 0)

    delta = abs(first_score - second_score)
    logger.info(f"[CONSISTENCY] Score delta: {first_score} vs {second_score} = Δ{delta}")

    if delta <= 3:
        # Scores are close enough — use the HIGHER score (benefit of doubt)
        if second_score >= first_score:
            logger.info("[CONSISTENCY] Second pass score >= first. Using second pass results.")
            return second_all
        else:
            logger.info("[CONSISTENCY] First pass score higher. Keeping first pass results.")
            return first_issues
    else:
        # Large delta — average the AI deductions to stabilize
        logger.warning(f"[CONSISTENCY] Large delta ({delta}). Averaging AI deductions.")
        # Use first pass issues but cap AI deductions to average
        first_ai = [i for i in first_issues if i.get("_source") == "ai"]
        first_total = sum(i.get("recoverable_marks", 0) for i in first_ai)
        second_total = sum(i.get("recoverable_marks", 0) for i in second_ai_issues)
        avg_total = (first_total + second_total) / 2

        # Scale first-pass AI deductions to match the average
        if first_total > 0:
            scale = avg_total / first_total
            for issue in first_ai:
                original = issue.get("recoverable_marks", 0)
                issue["recoverable_marks"] = max(1, round(original * scale))

        return first_issues


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
    Deterministic evaluation pipeline.

    Architecture:
      1. Deterministic section parser (regex, no AI)
      2. Rule engine (checklist validation, no AI)
      3. AI evaluation (temp=0, parallel, explanations only)
      4. Consistency verification (double-run in Deep Mode)
      5. Deterministic Python scoring
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

    # ── Helper: update progress ───────────────────────────────────────────────
    def _update_progress(section_name: str, status: str) -> None:
        if progress_store is not None:
            if "section_progress" not in progress_store:
                progress_store["section_progress"] = {}
            progress_store["section_progress"][section_name] = status

            completed = sum(
                1 for s in progress_store["section_progress"].values()
                if s in ("completed", "missing", "skipped")
            )
            total = len(progress_store["section_progress"])
            progress_store["progress"] = (
                f"Evaluating sections… {completed}/{total} complete"
            )

    # ── 1. Detect document type (deterministic, no AI) ────────────────────────
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

    # ── 2. DETERMINISTIC section extraction (regex, NO AI) ────────────────────
    t0 = time.monotonic()
    if progress_store is not None:
        progress_store["progress"] = "Parsing document sections…"

    sections = await asyncio.to_thread(parse_thesis_sections, text)
    extraction_confidences = await asyncio.to_thread(get_extraction_confidences, text, sections)
    timings["extraction_s"] = round(time.monotonic() - t0, 2)

    detected = [k for k, v in sections.items() if v and v.strip()]
    if progress_store is not None:
        progress_store["progress"] = f"Sections detected: {', '.join(detected)}"
        progress_store["detected_sections"] = detected
    logger.info(f"Sections parsed in {timings['extraction_s']}s: {detected}")

    # ── 3. RULE ENGINE — deterministic checks (NO AI) ─────────────────────────
    t0 = time.monotonic()
    if progress_store is not None:
        progress_store["progress"] = "Running checklist validation…"

    rule_issues = await asyncio.to_thread(run_rule_checks, sections)
    timings["rule_engine_s"] = round(time.monotonic() - t0, 2)
    logger.info(f"Rule engine: {len(rule_issues)} deterministic issues in {timings['rule_engine_s']}s")

    # ── 4. Build section task list for AI evaluation ──────────────────────────
    section_map = get_section_mapping(institution)
    rubric_data = load_rubric(institution)

    # Pre-populate section_progress
    if progress_store is not None:
        progress_store["section_progress"] = {
            rubric_name: ("skipped" if thesis_key in skip_keys else "pending")
            for thesis_key, rubric_name in section_map.items()
        }

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
            thesis_key=thesis_key,
            institution=institution,
            feedback_style=feedback_style,
            evaluation_mode=evaluation_mode,
            progress_callback=_update_progress,
        )
        section_tasks.append(coro)
        section_order.append(rubric_section)

    # ── 5. Run ALL section evaluations in parallel ────────────────────────────
    t0 = time.monotonic()
    if progress_store is not None:
        progress_store["progress"] = f"Running {len(section_tasks)} AI evaluations in parallel…"

    logger.info(f"Launching {len(section_tasks)} section evaluations in parallel…")
    section_results = await asyncio.gather(*section_tasks, return_exceptions=True)
    timings["section_evaluation_s"] = round(time.monotonic() - t0, 2)
    logger.info(f"All section evaluations completed in {timings['section_evaluation_s']}s")

    # ── 6. Merge rule-engine + AI issues ──────────────────────────────────────
    all_issues: List[Dict] = list(rule_issues)  # Rule engine issues first (deterministic)

    for i, result in enumerate(section_results):
        if isinstance(result, Exception):
            rubric_section = section_order[i]
            logger.error(f"Section '{rubric_section}' raised exception: {result}")
            continue

        issues: List[Dict] = result or []
        all_issues.extend(issues)

    # ── 7. Consistency verification (DEEP MODE only) ──────────────────────────
    if evaluation_mode == "deep":
        t0 = time.monotonic()
        if progress_store is not None:
            progress_store["progress"] = "Verifying scoring consistency…"

        first_scoring = calculate_score(all_issues, institution)
        first_score = first_scoring.get("overall_score", 0)

        all_issues = await _verify_consistency(
            sections=sections,
            section_map=section_map,
            rubric_data=rubric_data,
            first_score=first_score,
            first_issues=all_issues,
            institution=institution,
            feedback_style=feedback_style,
            evaluation_mode=evaluation_mode,
            progress_callback=_update_progress,
        )
        timings["consistency_s"] = round(time.monotonic() - t0, 2)
        logger.info(f"Consistency verification in {timings['consistency_s']}s")

    # ── 8. Cross-Section Validation (DEEP MODE only) ──────────────────────────
    cross_validation_result: Dict[str, Any] = {
        "validations": [],
        "total_deductions": 0,
        "summary": "Cross-section validation skipped (Fast Mode).",
    }

    if evaluation_mode == "deep":
        from .validation_engine import run_cross_validation_async
        t0 = time.monotonic()
        if progress_store is not None:
            progress_store["progress"] = "Running cross-section validation…"

        cross_validation_result = await run_cross_validation_async(sections)
        timings["cross_validation_s"] = round(time.monotonic() - t0, 2)
        logger.info(f"Cross-validation completed in {timings['cross_validation_s']}s")

    # ── 9. Deterministic Python scoring ──────────────────────────────────────
    t0 = time.monotonic()
    scoring_result = calculate_score(all_issues, institution)
    scoring_result["overall_score"] -= cross_validation_result["total_deductions"]
    scoring_result["cross_validation"] = cross_validation_result
    timings["scoring_s"] = round(time.monotonic() - t0, 3)

    # Clamp score to 0
    if scoring_result["overall_score"] < 0:
        scoring_result["overall_score"] = 0

    if adjusted_total is not None:
        scoring_result["total_marks"] = adjusted_total
        if scoring_result["overall_score"] > adjusted_total:
            scoring_result["overall_score"] = adjusted_total

    # ── 10. Attach metadata ──────────────────────────────────────────────────
    timings["total_s"] = round(time.monotonic() - pipeline_start, 2)

    scoring_result["sections"]               = sections
    scoring_result["institution"]            = institution
    scoring_result["document_type"]          = doc_classification
    scoring_result["feedback_style"]         = feedback_style
    scoring_result["extraction_confidences"] = extraction_confidences
    scoring_result["skipped_sections"]       = skip_keys
    scoring_result["evaluation_mode"]        = evaluation_mode
    scoring_result["rule_engine_issues"]     = len(rule_issues)
    scoring_result["ai_issues"]              = len([i for i in all_issues if i.get("_source") == "ai"])

    if debug:
        scoring_result["_timings"] = timings

    if progress_store is not None:
        progress_store["progress"] = "Evaluation complete."

    logger.info(
        f"[{evaluation_mode.upper()}] Evaluation complete in {timings['total_s']}s. "
        f"Score: {scoring_result.get('overall_score', 'N/A')}/{scoring_result.get('total_marks', 100)} "
        f"(rules={len(rule_issues)}, ai={scoring_result['ai_issues']})"
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
    Maintains full backward compatibility.
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
