"""
Deterministic Thesis Section Parser

Replaces AI-based section extraction with regex + heading normalization.
Zero AI calls. 100% deterministic. Same document → same sections every time.

Supports Nigerian thesis heading variations:
  CHAPTER ONE, Chapter 1, 1.0 INTRODUCTION, etc.
"""
import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("thesis_ai.section_parser")

# ── Minimum section thresholds (chars) ─────────────────────────────────────────
# Sections below these thresholds are considered missing.
MIN_SECTION_CHARS = {
    "abstract":   150,
    "chapter1":   800,
    "chapter2":   800,
    "chapter3":   800,
    "chapter4":   800,
    "chapter5":   800,
    "references": 300,
}

# ── Heading patterns ──────────────────────────────────────────────────────────
# Each entry: (canonical_key, list_of_regex_patterns)
# Patterns are tried top-to-bottom; first match wins for each section.

# Word-number mappings
_NUM_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}

# Build heading patterns for each section
SECTION_HEADING_PATTERNS: Dict[str, List[re.Pattern]] = {
    "abstract": [
        re.compile(r'^\s*ABSTRACT\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*PRELIMINARY\s+PAGES?\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*TITLE\s+PAGE\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter1": [
        re.compile(r'^\s*CHAPTER\s+(?:ONE|1)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*1\.0\s+', re.MULTILINE),
        re.compile(r'^\s*INTRODUCTION\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*BACKGROUND\s+(?:TO|OF)\s+(?:THE\s+)?STUDY\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter2": [
        re.compile(r'^\s*CHAPTER\s+(?:TWO|2)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*2\.0\s+', re.MULTILINE),
        re.compile(r'^\s*(?:REVIEW\s+OF\s+)?(?:RELATED\s+)?LITERATURE\s*(?:REVIEW)?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*LITERATURE\s+REVIEW\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter3": [
        re.compile(r'^\s*CHAPTER\s+(?:THREE|3)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*3\.0\s+', re.MULTILINE),
        re.compile(r'^\s*(?:RESEARCH\s+)?METHODOLOGY\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*METHODS?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*MATERIALS?\s+AND\s+METHODS?\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter4": [
        re.compile(r'^\s*CHAPTER\s+(?:FOUR|4)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*4\.0\s+', re.MULTILINE),
        # Multi-word compound phrases only — no standalone "RESULTS" to avoid false matches
        re.compile(r'^\s*PRESENTATION\s+OF\s+RESULTS?\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*DATA\s+PRESENTATION\s+AND\s+ANALYSIS\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*DATA\s+PRESENTATION\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*RESULTS?\s+AND\s+DISCUSSION\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*ANALYSIS\s+AND\s+INTERPRETATION\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter5": [
        re.compile(r'^\s*CHAPTER\s+(?:FIVE|5)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*5\.0\s+', re.MULTILINE),
        # Multi-word compound phrases only — no standalone "DISCUSSION" or "SUMMARY"
        re.compile(r'^\s*DISCUSSION\s+OF\s+FINDINGS?\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*SUMMARY\s*,?\s*CONCLUSION\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*SUMMARY\s+OF\s+(?:THE\s+)?(?:STUDY|FINDINGS?)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CONCLUSION\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*DISCUSSION\s*,?\s+CONCLUSION\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
    ],
    "references": [
        re.compile(r'^\s*REFERENCES?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*BIBLIOGRAPHY\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*LIST\s+OF\s+REFERENCES?\b', re.IGNORECASE | re.MULTILINE),
    ],
}

# Subsection aliases (used for confidence boosting)
SECTION_SUBSECTION_SIGNALS: Dict[str, List[str]] = {
    "chapter1": [
        "background", "statement of problem", "objectives", "research question",
        "hypothesis", "significance", "scope", "definition of terms",
        "operational definition", "purpose of study",
    ],
    "chapter2": [
        "conceptual", "theoretical", "empirical", "framework",
        "review of related", "literature",
    ],
    "chapter3": [
        "research design", "setting", "population", "sampling",
        "instrument", "validity", "reliability", "data collection",
        "data analysis", "ethical", "sample size",
    ],
    "chapter4": [
        "table", "figure", "result", "finding", "presentation",
        "research question", "hypothesis", "data",
    ],
    "chapter5": [
        "summary", "conclusion", "recommendation", "implication",
        "limitation", "suggestion", "finding", "discussion",
    ],
    "references": [
        "et al", "journal", "vol.", "pp.", "retrieved from",
        "doi:", "https://", "http://",
    ],
    "abstract": [
        "keyword", "abstract", "acknowledgment", "table of contents",
        "dedication", "list of tables", "list of figures",
    ],
}


# ── Core parser ────────────────────────────────────────────────────────────────

def _find_all_headings(text: str) -> List[Tuple[str, int, str]]:
    """
    Scan the full text and find ALL section heading matches.
    Returns: list of (canonical_key, char_position, matched_text)
    Sorted by position in document.
    """
    matches: List[Tuple[str, int, str]] = []

    for section_key, patterns in SECTION_HEADING_PATTERNS.items():
        for pattern in patterns:
            for m in pattern.finditer(text):
                matches.append((section_key, m.start(), m.group().strip()))

    # Sort by position in document
    matches.sort(key=lambda x: x[1])

    # Deduplicate: keep only the FIRST match per section key
    seen_keys = set()
    deduped: List[Tuple[str, int, str]] = []
    for key, pos, matched in matches:
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append((key, pos, matched))

    return deduped


def _extract_section_text(
    text: str,
    headings: List[Tuple[str, int, str]],
    section_key: str,
) -> str:
    """
    Extract the text for a specific section based on heading positions.
    Text runs from this section's heading to the next section's heading.
    """
    # Find this section's heading
    section_idx = None
    for i, (key, pos, _) in enumerate(headings):
        if key == section_key:
            section_idx = i
            break

    if section_idx is None:
        return ""

    start_pos = headings[section_idx][1]

    # End position: start of NEXT heading, or end of document
    if section_idx + 1 < len(headings):
        end_pos = headings[section_idx + 1][1]
    else:
        end_pos = len(text)

    return text[start_pos:end_pos].strip()


def _calculate_section_confidence(
    section_key: str,
    section_text: str,
    heading_found: bool,
) -> float:
    """
    Calculate extraction confidence for a section.
    Based on:
      1. Whether a heading was found (strongest signal)
      2. Text length vs threshold
      3. Presence of expected subsection keywords
    Returns: 0.0–1.0
    """
    if not section_text:
        return 0.0

    threshold = MIN_SECTION_CHARS.get(section_key, 800)
    text_len = len(section_text.strip())

    if text_len < threshold:
        return 0.0  # Below threshold = missing

    confidence = 0.0

    # Heading match is the strongest signal
    if heading_found:
        confidence += 0.50
    else:
        confidence += 0.10

    # Length bonus
    if text_len > threshold * 3:
        confidence += 0.25
    elif text_len > threshold:
        confidence += 0.15

    # Subsection keyword matches
    signals = SECTION_SUBSECTION_SIGNALS.get(section_key, [])
    text_lower = section_text.lower()
    signal_hits = sum(1 for s in signals if s in text_lower)
    if signal_hits >= 3:
        confidence += 0.20
    elif signal_hits >= 1:
        confidence += 0.10

    return min(round(confidence, 2), 0.95)


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_thesis_sections(text: str) -> Dict[str, str]:
    """
    Deterministic thesis section parser.

    Extracts sections using regex heading detection.
    No AI calls. Same input → same output every time.

    Returns: dict with keys:
      abstract, chapter1, chapter2, chapter3, chapter4, chapter5, references
    Each value is the full text of that section, or "" if not found.
    """
    if not text or len(text.strip()) < 100:
        logger.warning("Document too short for section parsing")
        return {k: "" for k in MIN_SECTION_CHARS}

    # Find all section headings
    headings = _find_all_headings(text)
    logger.info(f"Detected {len(headings)} section headings: {[(k, m) for k, _, m in headings]}")

    # Handle documents with NO headings at all
    if not headings:
        logger.warning("No section headings found — treating entire document as chapter1")
        return {
            "abstract": "",
            "chapter1": text.strip() if len(text.strip()) >= MIN_SECTION_CHARS["chapter1"] else "",
            "chapter2": "",
            "chapter3": "",
            "chapter4": "",
            "chapter5": "",
            "references": "",
        }

    # Handle abstract: if no explicit abstract heading, take everything before first chapter heading
    result: Dict[str, str] = {}
    first_chapter_pos = None
    for key, pos, _ in headings:
        if key.startswith("chapter"):
            first_chapter_pos = pos
            break

    # If no abstract heading found but there is text before first chapter
    abstract_heading_found = any(k == "abstract" for k, _, _ in headings)
    if not abstract_heading_found and first_chapter_pos and first_chapter_pos > 200:
        result["abstract"] = text[:first_chapter_pos].strip()
    else:
        result["abstract"] = _extract_section_text(text, headings, "abstract")

    # Extract remaining sections
    for key in ["chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]:
        result[key] = _extract_section_text(text, headings, key)

    # Apply minimum thresholds
    for key, min_chars in MIN_SECTION_CHARS.items():
        if key in result and len(result[key].strip()) < min_chars:
            if result[key].strip():
                logger.info(
                    f"Section '{key}' below threshold: {len(result[key].strip())} < {min_chars} chars. "
                    f"Marking as empty."
                )
            result[key] = ""

    # Log results
    detected = [k for k, v in result.items() if v]
    missing = [k for k, v in result.items() if not v]
    logger.info(f"Parsed sections — detected: {detected}, missing: {missing}")

    return result


def get_extraction_confidences(text: str, sections: Dict[str, str]) -> Dict[str, float]:
    """
    Calculate extraction confidence for all sections.
    Returns: dict of section_key → confidence (0.0–1.0)
    """
    headings = _find_all_headings(text)
    heading_keys = {k for k, _, _ in headings}

    confidences = {}
    for key in MIN_SECTION_CHARS:
        section_text = sections.get(key, "")
        heading_found = key in heading_keys
        confidences[key] = _calculate_section_confidence(key, section_text, heading_found)

    return confidences
