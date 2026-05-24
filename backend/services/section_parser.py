"""
Deterministic Thesis Section Parser — v2 (Hardened for real DOCX/PDF)

Replaces AI-based section extraction with regex + heading normalization.
Zero AI calls for primary parsing. 100% deterministic.

CRITICAL FIXES over v1:
  - Text pre-normalization: handles DOCX artifacts (tabs, non-breaking spaces,
    multiple spaces, page breaks, BOM characters)
  - Looser heading patterns: handles inline headings, mixed whitespace,
    headings not on their own line
  - AI FALLBACK: if regex finds < 3 sections on a long doc, falls back to
    AI-based extraction as safety net (still deterministic with temp=0)
  - Content-based section detection: if headings aren't found, scan for
    subsection keywords to infer section boundaries

Supports Nigerian thesis heading variations:
  CHAPTER ONE, Chapter One, CHAPTER 1, 1.0 INTRODUCTION, etc.
"""
import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("thesis_ai.section_parser")

# ── Minimum section thresholds (chars) ─────────────────────────────────────────
MIN_SECTION_CHARS = {
    "abstract":   150,
    "chapter1":   800,
    "chapter2":   800,
    "chapter3":   800,
    "chapter4":   800,
    "chapter5":   800,
    "references": 300,
}

ALL_SECTION_KEYS = ["abstract", "chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]


# ── Text normalization ─────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """
    Normalize extracted text to make heading detection reliable.
    Handles DOCX/PDF extraction artifacts.
    """
    # Remove BOM and zero-width characters
    text = text.replace('\ufeff', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')

    # Replace non-breaking spaces with regular spaces
    text = text.replace('\xa0', ' ')

    # Replace tabs with spaces
    text = text.replace('\t', ' ')

    # Replace form feed / page break characters with newlines
    text = text.replace('\f', '\n').replace('\x0c', '\n')

    # Normalize Windows line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse multiple spaces on same line (but preserve newlines)
    text = re.sub(r'[^\S\n]+', ' ', text)

    # Collapse 3+ consecutive newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Trim leading/trailing whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


# ── Heading patterns ──────────────────────────────────────────────────────────
# Patterns use \n or ^ anchoring after normalization.
# Each pattern matches the heading TEXT — we search line-by-line AND via regex.

# Primary patterns (strongest, most specific)
_CHAPTER_PATTERNS: Dict[str, List[re.Pattern]] = {
    "abstract": [
        re.compile(r'^\s*ABSTRACT\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*ABSTRACT\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*PRELIMINARY\s+PAGES?\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter1": [
        re.compile(r'^\s*CHAPTER\s+(?:ONE|1)\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:ONE|1)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*1\.0\s+INTRODUCTION\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*1\.0\s+', re.MULTILINE),
        re.compile(r'^\s*INTRODUCTION\s*$', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter2": [
        re.compile(r'^\s*CHAPTER\s+(?:TWO|2)\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:TWO|2)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*2\.0\s+(?:REVIEW|LITERATURE)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*2\.0\s+', re.MULTILINE),
        re.compile(r'^\s*LITERATURE\s+REVIEW\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*REVIEW\s+OF\s+(?:RELATED\s+)?LITERATURE\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter3": [
        re.compile(r'^\s*CHAPTER\s+(?:THREE|3)\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:THREE|3)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*3\.0\s+(?:RESEARCH\s+)?METHODOLOGY\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*3\.0\s+', re.MULTILINE),
        re.compile(r'^\s*(?:RESEARCH\s+)?METHODOLOGY\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*MATERIALS?\s+AND\s+METHODS?\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter4": [
        re.compile(r'^\s*CHAPTER\s+(?:FOUR|4)\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:FOUR|4)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*4\.0\s+(?:PRESENTATION|RESULTS?|DATA)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*4\.0\s+', re.MULTILINE),
        re.compile(r'^\s*PRESENTATION\s+OF\s+RESULTS?\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*DATA\s+PRESENTATION\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*RESULTS?\s+AND\s+DISCUSSION\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter5": [
        re.compile(r'^\s*CHAPTER\s+(?:FIVE|5)\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:FIVE|5)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*5\.0\s+(?:DISCUSSION|SUMMARY|CONCLUSION)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*5\.0\s+', re.MULTILINE),
        re.compile(r'^\s*DISCUSSION\s+OF\s+FINDINGS?\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*SUMMARY\s*,?\s*CONCLUSION\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*SUMMARY\s+OF\s+(?:THE\s+)?(?:STUDY|FINDINGS?)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CONCLUSION\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
    ],
    "references": [
        re.compile(r'^\s*REFERENCES?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*BIBLIOGRAPHY\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*LIST\s+OF\s+REFERENCES?\b', re.IGNORECASE | re.MULTILINE),
    ],
}

# Content-based signals for each section (used for fallback detection)
_SECTION_SIGNALS: Dict[str, List[str]] = {
    "chapter1": [
        "background to the study", "background of the study",
        "statement of problem", "statement of the problem",
        "objectives of the study", "objective of the study",
        "research questions", "research hypothesis",
        "significance of the study", "scope of the study",
        "operational definition of terms", "definition of terms",
        "purpose of the study", "purpose of study",
    ],
    "chapter2": [
        "conceptual review", "conceptual framework",
        "theoretical framework", "theoretical review",
        "empirical review", "review of related literature",
        "review of literature",
    ],
    "chapter3": [
        "research design", "study design",
        "target population", "study population",
        "sampling technique", "sampling method",
        "instrument for data collection", "instruments for data collection",
        "validity of instrument", "reliability of instrument",
        "method of data collection", "method of data analysis",
        "ethical consideration", "ethical approval",
        "sample size",
    ],
    "chapter4": [
        "presentation of results", "data presentation",
        "table 1", "table 2", "table 3",
        "figure 1", "figure 2",
        "analysis of data",
    ],
    "chapter5": [
        "summary of findings", "summary of the study",
        "discussion of findings", "discussion of results",
        "conclusion", "recommendations",
        "limitations of the study", "limitation of the study",
        "suggestions for further studies", "suggestion for further",
        "implication of findings", "implications of findings",
    ],
    "references": [
        "et al.", "et al,", "retrieved from",
        "doi:", "https://doi", "journal of",
        "vol.", "pp.",
    ],
    "abstract": [
        "keywords:", "key words:",
        "table of contents", "list of tables",
        "list of figures", "acknowledgment",
        "dedication", "certification", "declaration",
    ],
}


# ── Core parser ────────────────────────────────────────────────────────────────

def _find_all_headings(text: str) -> List[Tuple[str, int, str]]:
    """
    Scan normalized text and find ALL section heading matches.
    Returns: list of (canonical_key, char_position, matched_text)
    Sorted by position. Deduplicated to first match per section.
    """
    matches: List[Tuple[str, int, str]] = []

    for section_key, patterns in _CHAPTER_PATTERNS.items():
        for pattern in patterns:
            for m in pattern.finditer(text):
                matches.append((section_key, m.start(), m.group().strip()))

    # Sort by position
    matches.sort(key=lambda x: x[1])

    # Deduplicate: first match per section key
    seen = set()
    result: List[Tuple[str, int, str]] = []
    for key, pos, matched in matches:
        if key not in seen:
            seen.add(key)
            result.append((key, pos, matched))

    return result


def _extract_section_text(
    text: str,
    headings: List[Tuple[str, int, str]],
    section_key: str,
) -> str:
    """Extract text between this heading and the next heading."""
    idx = None
    for i, (key, pos, _) in enumerate(headings):
        if key == section_key:
            idx = i
            break

    if idx is None:
        return ""

    start = headings[idx][1]
    end = headings[idx + 1][1] if idx + 1 < len(headings) else len(text)

    return text[start:end].strip()


def _content_based_split(text: str) -> Dict[str, str]:
    """
    FALLBACK: When regex heading detection fails, scan for subsection
    keywords to infer where each chapter starts.

    This handles documents where:
      - Headings are bold/styled but extracted as plain inline text
      - Heading text is merged with body text
      - No clear line-break before headings
    """
    logger.info("Running content-based fallback section detection...")
    text_lower = text.lower()
    result: Dict[str, str] = {k: "" for k in ALL_SECTION_KEYS}

    # Find the position of each section's earliest distinctive signal
    section_positions: List[Tuple[str, int]] = []

    for section_key, signals in _SECTION_SIGNALS.items():
        best_pos = len(text)
        signal_count = 0

        for signal in signals:
            pos = text_lower.find(signal)
            if pos != -1:
                signal_count += 1
                if pos < best_pos:
                    best_pos = pos

        # Only accept if we found at least 2 signals for this section
        if signal_count >= 2 and best_pos < len(text):
            # Walk backwards to find the start of the line
            line_start = text_lower.rfind('\n', 0, best_pos)
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            section_positions.append((section_key, line_start))
            logger.info(f"  Content signal: {section_key} at pos {line_start} ({signal_count} signals)")

    if not section_positions:
        logger.warning("Content-based detection found no sections")
        return result

    # Sort by position
    section_positions.sort(key=lambda x: x[1])

    # Extract text between positions
    for i, (key, start) in enumerate(section_positions):
        end = section_positions[i + 1][1] if i + 1 < len(section_positions) else len(text)
        section_text = text[start:end].strip()
        min_chars = MIN_SECTION_CHARS.get(key, 800)
        if len(section_text) >= min_chars:
            result[key] = section_text

    detected = [k for k, v in result.items() if v]
    logger.info(f"Content-based detection found {len(detected)} sections: {detected}")
    return result


def _calculate_section_confidence(
    section_key: str,
    section_text: str,
    heading_found: bool,
) -> float:
    """Calculate extraction confidence (0.0–1.0)."""
    if not section_text:
        return 0.0

    threshold = MIN_SECTION_CHARS.get(section_key, 800)
    text_len = len(section_text.strip())

    if text_len < threshold:
        return 0.0

    confidence = 0.0

    if heading_found:
        confidence += 0.50
    else:
        confidence += 0.15  # Content-based detection

    if text_len > threshold * 3:
        confidence += 0.25
    elif text_len > threshold:
        confidence += 0.15

    signals = _SECTION_SIGNALS.get(section_key, [])
    text_lower = section_text.lower()
    hits = sum(1 for s in signals if s in text_lower)
    if hits >= 3:
        confidence += 0.20
    elif hits >= 1:
        confidence += 0.10

    return min(round(confidence, 2), 0.95)


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_thesis_sections(text: str) -> Dict[str, str]:
    """
    Deterministic thesis section parser with multi-layer fallback.

    Layer 1: Regex heading detection (fastest, most reliable)
    Layer 2: Content-based keyword detection (fallback for messy DOCX)
    Layer 3: AI extraction fallback (safety net, still temp=0)

    Same input → same output every time.
    """
    if not text or len(text.strip()) < 100:
        logger.warning("Document too short for section parsing")
        return {k: "" for k in ALL_SECTION_KEYS}

    # Normalize text for reliable matching
    normalized = _normalize_text(text)
    doc_length = len(normalized)
    logger.info(f"Section parsing: {doc_length} chars (normalized)")

    # ── Layer 1: Regex heading detection ──────────────────────────────────────
    headings = _find_all_headings(normalized)
    logger.info(f"Regex detected {len(headings)} headings: {[(k, m) for k, _, m in headings]}")

    result: Dict[str, str] = {}

    if headings:
        # Handle abstract: if no heading, take everything before first chapter
        first_chapter_pos = None
        for key, pos, _ in headings:
            if key.startswith("chapter"):
                first_chapter_pos = pos
                break

        has_abstract_heading = any(k == "abstract" for k, _, _ in headings)
        if not has_abstract_heading and first_chapter_pos and first_chapter_pos > 100:
            result["abstract"] = normalized[:first_chapter_pos].strip()
        else:
            result["abstract"] = _extract_section_text(normalized, headings, "abstract")

        for key in ["chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]:
            result[key] = _extract_section_text(normalized, headings, key)

    # Count how many sections we actually found (above threshold)
    found_count = 0
    for key in ALL_SECTION_KEYS:
        section_text = result.get(key, "")
        min_chars = MIN_SECTION_CHARS.get(key, 800)
        if section_text and len(section_text.strip()) >= min_chars:
            found_count += 1

    # ── Layer 2: Content-based fallback ───────────────────────────────────────
    # If regex found < 3 sections AND doc is long enough to have chapters
    if found_count < 3 and doc_length > 5000:
        logger.warning(
            f"Regex only found {found_count} sections in a {doc_length}-char document. "
            f"Trying content-based fallback..."
        )
        content_result = _content_based_split(normalized)
        content_found = sum(1 for v in content_result.values() if v)

        if content_found > found_count:
            logger.info(f"Content-based found {content_found} sections (vs regex {found_count}). Using content results.")
            # Merge: prefer regex results where they exist, fill gaps with content-based
            for key in ALL_SECTION_KEYS:
                existing = result.get(key, "")
                min_chars = MIN_SECTION_CHARS.get(key, 800)
                if not existing or len(existing.strip()) < min_chars:
                    if content_result.get(key):
                        result[key] = content_result[key]

    # ── Layer 3: AI fallback ──────────────────────────────────────────────────
    # Recount after content-based
    final_count = 0
    for key in ALL_SECTION_KEYS:
        section_text = result.get(key, "")
        min_chars = MIN_SECTION_CHARS.get(key, 800)
        if section_text and len(section_text.strip()) >= min_chars:
            final_count += 1

    if final_count < 3 and doc_length > 5000:
        logger.warning(
            f"Both regex and content-based found only {final_count} sections. "
            f"Falling back to AI extraction..."
        )
        try:
            ai_result = _ai_extraction_fallback(normalized)
            ai_found = sum(1 for v in ai_result.values() if v and len(v.strip()) >= MIN_SECTION_CHARS.get("chapter1", 800))

            if ai_found > final_count:
                logger.info(f"AI fallback found {ai_found} sections. Merging.")
                for key in ALL_SECTION_KEYS:
                    existing = result.get(key, "")
                    min_chars = MIN_SECTION_CHARS.get(key, 800)
                    if not existing or len(existing.strip()) < min_chars:
                        ai_text = ai_result.get(key, "")
                        if ai_text and len(ai_text.strip()) >= min_chars:
                            result[key] = ai_text
        except Exception as e:
            logger.error(f"AI fallback failed: {e}")

    # ── Apply minimum thresholds ──────────────────────────────────────────────
    for key in ALL_SECTION_KEYS:
        if key not in result:
            result[key] = ""
        section_text = result[key]
        min_chars = MIN_SECTION_CHARS.get(key, 800)
        if section_text and len(section_text.strip()) < min_chars:
            logger.info(f"Section '{key}': {len(section_text.strip())} chars < {min_chars} threshold → empty")
            result[key] = ""

    detected = [k for k, v in result.items() if v]
    missing = [k for k, v in result.items() if not v]
    logger.info(f"Final sections — detected: {detected}, missing: {missing}")

    return result


def _ai_extraction_fallback(text: str) -> Dict[str, str]:
    """
    Last-resort AI extraction when regex + content-based both fail.
    Uses temp=0 for determinism. Only called when document is clearly
    long enough to contain chapters but headings can't be detected.
    """
    from .ai.router import get_router

    system_prompt = """
    You are a document parser. Split this thesis text into sections.
    Return ONLY valid JSON with these exact keys:
    {
      "abstract": "full text or empty string",
      "chapter1": "full text or empty string",
      "chapter2": "full text or empty string",
      "chapter3": "full text or empty string",
      "chapter4": "full text or empty string",
      "chapter5": "full text or empty string",
      "references": "full text or empty string"
    }
    Rules:
    - Extract the FULL text for each section. Do not summarize.
    - If a section is not present, return empty string "".
    - Do NOT hallucinate content.
    """

    # Truncate to avoid token limits
    max_chars = 100000
    if len(text) > max_chars:
        text = text[:max_chars]

    router = get_router()
    result = router.generate(system_prompt, f"Thesis text:\n{text}", task="extract_sections")
    result.pop("_meta", None)

    for key in ALL_SECTION_KEYS:
        if key not in result or result[key] is None:
            result[key] = ""

    return result


def get_extraction_confidences(text: str, sections: Dict[str, str]) -> Dict[str, float]:
    """Calculate extraction confidence for all sections."""
    normalized = _normalize_text(text)
    headings = _find_all_headings(normalized)
    heading_keys = {k for k, _, _ in headings}

    return {
        key: _calculate_section_confidence(key, sections.get(key, ""), key in heading_keys)
        for key in ALL_SECTION_KEYS
    }
