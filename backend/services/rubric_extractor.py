"""
Adaptive Rubric Extractor

Extracts rubric structures from uploaded department handbooks, scoring guides,
and project format documents (PDF/DOCX).

Architecture:
  1. DETERMINISTIC extraction (regex, heading detection, mark patterns)
  2. SEMANTIC intent mapping (keyword-based section classification)
  3. AI fallback (Gemini Flash, temp=0) — only if deterministic finds < 3 sections
  4. Validation + fallback to nigeria_general if extraction fails

Confidence scoring:
  - Per-section confidence (0.0-1.0)
  - Overall confidence (weighted average)

Output matches rubric.json schema for direct use in evaluation pipeline.
"""
import json
import logging
import os
import re
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("thesis_ai.rubric_extractor")

# Debug mode: save extracted rubrics to temp folder
SAVE_DEBUG_RUBRICS = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
DEBUG_RUBRIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "debug_rubrics")


# -- Semantic Intent Mapping --------------------------------------------------
# Maps keyword groups to canonical section thesis_keys.
# Used to classify sections when headings are non-standard.

SECTION_INTENT_KEYWORDS = {
    "abstract": [
        "abstract", "preliminary", "title page", "declaration",
        "certification", "approval", "dedication", "acknowledgement",
        "table of contents", "list of tables", "list of figures",
    ],
    "chapter1": [
        "introduction", "background", "statement of problem",
        "statement of the problem", "problem statement",
        "objectives", "objective of the study", "aim",
        "research question", "hypothesis", "significance",
        "scope", "delimitation", "definition of terms",
        "operational definition", "purpose of study",
    ],
    "chapter2": [
        "literature review", "literature", "conceptual review",
        "conceptual framework", "theoretical framework",
        "theoretical review", "empirical review", "empirical",
        "review of related", "review of literature",
    ],
    "chapter3": [
        "methodology", "research methodology", "research design",
        "method", "methods", "materials and methods",
        "population", "sampling", "sample size",
        "instrument", "data collection", "data analysis",
        "validity", "reliability", "ethical consideration",
        "ethical approval",
    ],
    "chapter4": [
        "results", "findings", "data presentation",
        "data analysis", "presentation of results",
        "presentation of data", "empirical findings",
        "research question", "hypothesis testing",
    ],
    "chapter5": [
        "discussion", "conclusion", "recommendation",
        "summary", "summary of findings", "implication",
        "limitation", "suggestion for further",
        "discussion of findings",
    ],
    "references": [
        "references", "bibliography", "reference",
        "works cited", "list of references",
        "appendix", "appendices",
    ],
}

# -- Mark Extraction Patterns -------------------------------------------------

MARK_PATTERNS = [
    # "(10 marks)" or "(10 Marks)"
    re.compile(r'\((\d+(?:\.\d+)?)\s*marks?\)', re.IGNORECASE),
    # "10 marks" at end of line
    re.compile(r'(\d+(?:\.\d+)?)\s*marks?\s*$', re.IGNORECASE | re.MULTILINE),
    # "Total: 15" or "Total = 15" or "Total marks: 15"
    re.compile(r'total\s*(?:marks?)?\s*[:=]\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    # "10%" (percentage)
    re.compile(r'(\d+(?:\.\d+)?)\s*%', re.IGNORECASE),
    # "marks = 10" or "mark: 10"
    re.compile(r'marks?\s*[:=]\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    # "worth 10" or "carries 5 marks"
    re.compile(r'(?:worth|carries|carrying)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
]

# Section heading patterns for rubric documents
RUBRIC_HEADING_PATTERNS = [
    # "CHAPTER ONE" / "Chapter 1" / "1.0"
    re.compile(r'^\s*(?:CHAPTER\s+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|[1-6]))\s*[:.]?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    # "1.0 INTRODUCTION" / "2.0 LITERATURE REVIEW"
    re.compile(r'^\s*([1-6])\.0\s+(.*)', re.MULTILINE),
    # Section/Part numbering
    re.compile(r'^\s*(?:SECTION|PART)\s+([A-F1-6IViv]+)\s*[:.]?\s*(.*)', re.IGNORECASE | re.MULTILINE),
    # Standalone section names
    re.compile(r'^\s*(INTRODUCTION|LITERATURE\s+REVIEW|METHODOLOGY|RESULTS?|DISCUSSION|CONCLUSION|REFERENCES?|ABSTRACT|PRELIMINARY)\s*$', re.IGNORECASE | re.MULTILINE),
]

# Default marks for sections when extraction fails
DEFAULT_SECTION_MARKS = {
    "abstract": 10,
    "chapter1": 15,
    "chapter2": 15,
    "chapter3": 20,
    "chapter4": 15,
    "chapter5": 15,
    "references": 7,
}


# -- Core Extraction ----------------------------------------------------------

def _extract_text_from_file(file_path: str) -> str:
    """Extract text from uploaded file (PDF/DOCX). Reuses existing extraction."""
    from .extraction import extract_text
    return extract_text(file_path)


def _find_sections_deterministic(text: str) -> List[Dict[str, Any]]:
    """
    Phase 1: Deterministic section extraction using regex and keyword matching.

    Returns a list of extracted sections with:
      - heading: the detected heading text
      - thesis_key: canonical section key
      - marks: extracted mark value (or None)
      - criteria: list of extracted criteria
      - confidence: extraction confidence (0.0-1.0)
      - text_span: the text belonging to this section
    """
    sections = []
    text_lower = text.lower()
    lines = text.split('\n')

    # Step 1: Find heading-like lines
    heading_positions = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this line looks like a heading
        is_heading = False
        heading_text = stripped

        for pattern in RUBRIC_HEADING_PATTERNS:
            m = pattern.match(stripped)
            if m:
                is_heading = True
                heading_text = stripped
                break

        # Also detect by ALL CAPS + short length
        if not is_heading and stripped.isupper() and 3 < len(stripped) < 80:
            is_heading = True

        # Detect numbered items like "1. Introduction" or "A. Methodology"
        if not is_heading and re.match(r'^[A-Z1-9][.)]\s+\w', stripped):
            is_heading = True

        if is_heading:
            heading_positions.append((i, heading_text))

    # Step 2: Classify each heading using semantic intent mapping
    for idx, (line_num, heading_text) in enumerate(heading_positions):
        # Get text span (to next heading or end)
        start_line = line_num
        end_line = heading_positions[idx + 1][0] if idx + 1 < len(heading_positions) else len(lines)
        text_span = '\n'.join(lines[start_line:end_line])

        # Classify using keyword matching
        best_key = None
        best_score = 0
        combined_text = (heading_text + ' ' + text_span[:500]).lower()

        for thesis_key, keywords in SECTION_INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined_text)
            if score > best_score:
                best_score = score
                best_key = thesis_key

        if best_key is None or best_score < 1:
            continue

        # Extract marks from the section text
        marks = _extract_marks_from_text(text_span)

        # Extract criteria (sub-items with marks)
        criteria = _extract_criteria_from_text(text_span)

        # Calculate confidence
        confidence = _calculate_extraction_confidence(
            heading_found=True,
            marks_found=marks is not None,
            criteria_count=len(criteria),
            keyword_score=best_score,
        )

        sections.append({
            "heading": heading_text,
            "thesis_key": best_key,
            "marks": marks,
            "criteria": criteria,
            "confidence": round(confidence, 2),
            "text_span": text_span[:200],  # preview only
        })

    # Deduplicate: keep highest-confidence match per thesis_key
    deduped = {}
    for section in sections:
        key = section["thesis_key"]
        if key not in deduped or section["confidence"] > deduped[key]["confidence"]:
            deduped[key] = section

    return list(deduped.values())


def _extract_marks_from_text(text: str) -> Optional[float]:
    """Extract the total marks for a section from its text."""
    for pattern in MARK_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            # Return the largest number found (likely the total)
            values = [float(m) for m in matches if 0 < float(m) <= 100]
            if values:
                return max(values)
    return None


def _extract_criteria_from_text(text: str) -> Dict[str, float]:
    """
    Extract individual criteria and their marks from section text.

    Looks for patterns like:
      - "Background to the Study (3 marks)"
      - "1.1 Statement of Problem - 2 marks"
      - "Research Design: 1 mark"
    """
    criteria = {}
    lines = text.split('\n')

    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 5:
            continue

        # Pattern: "Criterion text (N marks)"
        m = re.match(
            r'^[\s\-•*\d.)\]]*\s*(.+?)\s*\((\d+(?:\.\d+)?)\s*marks?\)',
            stripped, re.IGNORECASE
        )
        if m:
            criterion = m.group(1).strip()
            marks = float(m.group(2))
            if criterion and 0 < marks <= 50:
                criteria[criterion] = marks
                continue

        # Pattern: "Criterion text - N marks" or ": N marks"
        m = re.match(
            r'^[\s\-•*\d.)\]]*\s*(.+?)\s*[-:]\s*(\d+(?:\.\d+)?)\s*marks?',
            stripped, re.IGNORECASE
        )
        if m:
            criterion = m.group(1).strip()
            marks = float(m.group(2))
            if criterion and 0 < marks <= 50:
                criteria[criterion] = marks

    return criteria


def _calculate_extraction_confidence(
    heading_found: bool,
    marks_found: bool,
    criteria_count: int,
    keyword_score: int,
) -> float:
    """
    Calculate per-section extraction confidence.

    Factors:
      - Heading detected: +0.30
      - Marks extracted: +0.25
      - Criteria found: +0.05 per criterion (max +0.25)
      - Keyword matches: +0.05 per keyword (max +0.20)
    """
    confidence = 0.0

    if heading_found:
        confidence += 0.30
    if marks_found:
        confidence += 0.25

    confidence += min(criteria_count * 0.05, 0.25)
    confidence += min(keyword_score * 0.05, 0.20)

    return min(confidence, 1.0)


# -- Build Rubric from Extracted Sections -------------------------------------

def _build_rubric_from_sections(
    sections: List[Dict[str, Any]],
    institution_name: str = "Adaptive Rubric",
) -> Dict[str, Any]:
    """
    Convert extracted sections into a rubric.json-compatible structure.

    Uses default marks for sections where marks weren't extracted.
    Normalizes total to 100 marks.
    """
    # Section display names
    KEY_TO_NAME = {
        "abstract": "Preliminary Pages",
        "chapter1": "Chapter One",
        "chapter2": "Chapter Two",
        "chapter3": "Chapter Three",
        "chapter4": "Chapter Four",
        "chapter5": "Chapter Five",
        "references": "References and Appendices",
    }

    rubric_sections = {}
    section_confidences = {}

    for section in sections:
        key = section["thesis_key"]
        name = KEY_TO_NAME.get(key, section.get("heading", key.title()))

        marks = section.get("marks")
        if marks is None:
            marks = DEFAULT_SECTION_MARKS.get(key, 10)

        criteria = section.get("criteria", {})
        if not criteria:
            # Generate default criteria from nigeria_general
            criteria = {f"{name} content quality": marks}

        rubric_sections[name] = {
            "total": marks,
            "thesis_key": key,
            "criteria": criteria,
        }
        section_confidences[key] = section.get("confidence", 0.5)

    # Fill in any missing required sections with defaults
    for key, default_marks in DEFAULT_SECTION_MARKS.items():
        name = KEY_TO_NAME.get(key, key.title())
        if name not in rubric_sections:
            rubric_sections[name] = {
                "total": default_marks,
                "thesis_key": key,
                "criteria": {f"{name} content quality": default_marks},
            }
            section_confidences[key] = 0.2  # low confidence for default-filled

    # Add formatting section
    if not any("format" in k.lower() for k in rubric_sections):
        rubric_sections["General Formatting"] = {
            "total": 3,
            "thesis_key": None,
            "criteria": {
                "Font, spacing, and formatting": 1.5,
                "Pagination and presentation": 1.5,
            },
        }

    # Normalize total to 100
    raw_total = sum(s["total"] for s in rubric_sections.values())
    if raw_total != 100 and raw_total > 0:
        scale = 100.0 / raw_total
        for section_data in rubric_sections.values():
            section_data["total"] = round(section_data["total"] * scale, 1)
            # Scale criteria too
            scaled_criteria = {}
            for c_name, c_marks in section_data["criteria"].items():
                scaled_criteria[c_name] = round(c_marks * scale, 1)
            section_data["criteria"] = scaled_criteria

    total_marks = round(sum(s["total"] for s in rubric_sections.values()), 1)

    # Calculate overall confidence
    if section_confidences:
        overall_confidence = sum(section_confidences.values()) / len(section_confidences)
    else:
        overall_confidence = 0.0

    return {
        "institution_name": institution_name,
        "institution_code": "adaptive",
        "total_marks": total_marks,
        "sections": rubric_sections,
        "_extraction_meta": {
            "overall_confidence": round(overall_confidence, 2),
            "section_confidences": section_confidences,
            "extraction_method": "deterministic",
        },
    }


# -- AI Fallback Extraction ---------------------------------------------------

async def _extract_with_ai_fallback(text: str) -> Optional[Dict[str, Any]]:
    """
    Phase 3: AI-assisted rubric extraction using Gemini Flash.
    Only called when deterministic extraction finds < 3 sections.

    Returns rubric dict or None on failure.
    """
    try:
        from .ai.router import get_router
        router = get_router()

        prompt = """You are extracting a grading rubric from an academic document.

Extract ALL sections, their marks, and criteria. Return STRICT JSON only.

Format:
{
  "sections": [
    {
      "name": "Chapter One",
      "thesis_key": "chapter1",
      "marks": 15,
      "criteria": {
        "Background to the Study": 3,
        "Statement of Problem": 2
      }
    }
  ]
}

RULES:
- thesis_key must be one of: abstract, chapter1, chapter2, chapter3, chapter4, chapter5, references
- marks must be positive numbers
- If marks are not specified, estimate based on typical Nigerian university standards
- Return ONLY the JSON, no explanation

Document text:
""" + text[:4000]  # Cap at 4000 chars

        response = await router.generate(
            prompt=prompt,
            model_preference="flash",
            temperature=0,
            max_tokens=2000,
        )

        # Parse JSON from response
        response_text = response.get("text", "") if isinstance(response, dict) else str(response)

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group())
            if "sections" in data:
                sections = []
                for s in data["sections"]:
                    sections.append({
                        "heading": s.get("name", ""),
                        "thesis_key": s.get("thesis_key", ""),
                        "marks": s.get("marks"),
                        "criteria": s.get("criteria", {}),
                        "confidence": 0.5,  # AI extractions get medium confidence
                    })
                return sections

    except Exception as e:
        logger.error(f"AI rubric extraction failed: {e}")

    return None


# -- Public API ---------------------------------------------------------------

def extract_rubric_from_text(
    text: str,
    institution_name: str = "Adaptive Rubric",
) -> Dict[str, Any]:
    """
    Extract a rubric structure from guideline text.

    Returns:
    {
        "rubric": {...},                    # rubric.json format
        "confidence": 0.85,                 # overall confidence
        "section_confidences": {...},       # per-section confidence
        "extraction_method": "deterministic" | "ai_assisted",
        "warnings": [...],
        "sections_found": 5,
        "sections_defaulted": 2,
    }
    """
    warnings = []

    # Phase 1: Deterministic extraction
    sections = _find_sections_deterministic(text)
    extraction_method = "deterministic"

    logger.info(f"Deterministic extraction found {len(sections)} sections")

    # Phase 2: Check if we need AI fallback
    if len(sections) < 3:
        logger.info("Low section count, attempting AI fallback...")
        warnings.append(
            f"Only {len(sections)} sections found by deterministic parser. "
            "Using AI-assisted extraction as fallback."
        )

        try:
            import asyncio
            ai_sections = asyncio.run(_extract_with_ai_fallback(text))
            if ai_sections and len(ai_sections) > len(sections):
                sections = ai_sections
                extraction_method = "ai_assisted"
                logger.info(f"AI fallback found {len(sections)} sections")
        except Exception as e:
            logger.error(f"AI fallback failed: {e}")
            warnings.append("AI-assisted extraction failed. Using defaults.")

    # Build rubric
    rubric = _build_rubric_from_sections(sections, institution_name)
    rubric["_extraction_meta"]["extraction_method"] = extraction_method

    # Count defaulted sections
    sections_found = len(sections)
    sections_defaulted = 7 - min(sections_found, 7)

    if sections_defaulted > 0:
        warnings.append(
            f"{sections_defaulted} section(s) could not be extracted. "
            "General Nigerian standards were used as fallback for those sections."
        )

    # Confidence warning
    overall_conf = rubric["_extraction_meta"]["overall_confidence"]
    if overall_conf < 0.6:
        warnings.append(
            "Overall extraction confidence is low. "
            "Please review the extracted rubric carefully before evaluating."
        )

    # Debug save
    if SAVE_DEBUG_RUBRICS:
        _save_debug_rubric(rubric, warnings)

    return {
        "rubric": rubric,
        "confidence": overall_conf,
        "section_confidences": rubric["_extraction_meta"]["section_confidences"],
        "extraction_method": extraction_method,
        "warnings": warnings,
        "sections_found": sections_found,
        "sections_defaulted": sections_defaulted,
    }


def extract_rubric_from_file(
    file_path: str,
    institution_name: str = "Adaptive Rubric",
) -> Dict[str, Any]:
    """
    Extract a rubric from an uploaded file (PDF/DOCX).
    Wrapper around extract_rubric_from_text that handles file I/O.
    """
    text = _extract_text_from_file(file_path)
    if not text or len(text.strip()) < 50:
        return {
            "rubric": None,
            "confidence": 0.0,
            "section_confidences": {},
            "extraction_method": "failed",
            "warnings": ["Could not extract text from the uploaded file."],
            "sections_found": 0,
            "sections_defaulted": 7,
        }

    return extract_rubric_from_text(text, institution_name)


def _save_debug_rubric(rubric: Dict, warnings: List[str]) -> None:
    """Save extracted rubric to debug folder. Auto-deletes after 24h."""
    try:
        os.makedirs(DEBUG_RUBRIC_DIR, exist_ok=True)
        timestamp = int(time.time())
        path = os.path.join(DEBUG_RUBRIC_DIR, f"rubric_{timestamp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"rubric": rubric, "warnings": warnings}, f, indent=2)
        logger.info(f"Debug rubric saved: {path}")

        # Clean up old debug rubrics (> 24h)
        cutoff = timestamp - 86400
        for fname in os.listdir(DEBUG_RUBRIC_DIR):
            fpath = os.path.join(DEBUG_RUBRIC_DIR, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                logger.debug(f"Cleaned up old debug rubric: {fname}")
    except Exception as e:
        logger.debug(f"Failed to save debug rubric: {e}")
