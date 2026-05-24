"""
Deterministic Thesis Section Parser — v3 (Table of Contents aware)

Replaces AI-based section extraction with regex + heading normalization.
Zero AI calls for primary parsing. 100% deterministic.

KEY FIX (v3): Table of Contents detection.
  Real Nigerian thesis DOCX files contain a Table of Contents that lists
  all chapter headings. The parser was matching TOC entries instead of
  actual chapter content. Now detects TOC boundaries and skips headings
  inside it, using the ACTUAL chapter headings further in the document.

FALLBACK CHAIN:
  Layer 1: Regex heading detection (with TOC-awareness)
  Layer 2: Content-based keyword detection
  Layer 3: AI extraction (temp=0, last resort)
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
    """Normalize extracted text to make heading detection reliable."""
    text = text.replace('\ufeff', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    text = text.replace('\xa0', ' ')
    text = text.replace('\t', ' ')
    text = text.replace('\f', '\n').replace('\x0c', '\n')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


# ── Table of Contents detection ───────────────────────────────────────────────

def _find_toc_boundaries(text: str) -> Tuple[int, int]:
    """
    Detect where the Table of Contents starts and ends.
    Returns (toc_start, toc_end) character positions, or (-1, -1) if not found.

    TOC is detected by:
      - A "Table of Contents" heading
      - Followed by many short lines (chapter listings)
      - Ending when we hit actual body content (long paragraphs)
    """
    toc_patterns = [
        re.compile(r'^\s*TABLE\s+OF\s+CONTENTS?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*TABLE\s+OF\s+CONTENT\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CONTENTS?\s*$', re.IGNORECASE | re.MULTILINE),
    ]

    toc_start = -1
    for pat in toc_patterns:
        m = pat.search(text)
        if m:
            toc_start = m.start()
            break

    if toc_start == -1:
        return (-1, -1)

    # Strategy: TOC ends when we hit REFERENCES (always last TOC entry in Nigerian theses)
    # or when we see a body-text paragraph (> 80 chars, not a heading).
    # CRITICAL: The CHAPTER ONE heading right after the TOC must NOT be inside the TOC.
    lines_after = text[toc_start:].split('\n')
    pos = toc_start
    toc_end = toc_start
    saw_references = False

    for i, line in enumerate(lines_after):
        stripped = line.strip()

        if i < 2:  # skip heading line + possible blank
            pos += len(line) + 1
            continue

        # If we already saw REFERENCES in the TOC, the next non-empty line
        # is body content — end the TOC HERE (before this line)
        if saw_references and stripped:
            toc_end = pos
            break

        # Check if this is a REFERENCES entry (last entry in Nigerian thesis TOC)
        if re.match(r'^\s*REFERENCES?\s*$', stripped, re.IGNORECASE):
            saw_references = True
            pos += len(line) + 1
            toc_end = pos
            continue

        # A long line that's not a heading → body content → end TOC
        if len(stripped) > 80:
            is_heading = bool(re.match(
                r'^\s*(?:CHAPTER|[0-9]+\.|ABSTRACT|REFERENCE|APPENDIX|LIST\s+OF)',
                stripped, re.IGNORECASE
            ))
            if not is_heading:
                toc_end = pos
                break

        pos += len(line) + 1
        toc_end = pos

    logger.info(f"TOC detected: pos {toc_start}..{toc_end} ({toc_end - toc_start} chars)")
    return (toc_start, toc_end)


# ── Heading patterns ──────────────────────────────────────────────────────────

_CHAPTER_PATTERNS: Dict[str, List[re.Pattern]] = {
    "abstract": [
        re.compile(r'^\s*ABSTRACT\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*ABSTRACT\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*PRELIMINARY\s+PAGES?\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter1": [
        re.compile(r'^\s*CHAPTER\s+(?:ONE|1)\s*[:.]?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:ONE|1)\s*[:.]?\s+\w', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:ONE|1)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*1\.0\s+INTRODUCTION\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*1\.0\s+', re.MULTILINE),
        re.compile(r'^\s*INTRODUCTION\s*$', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter2": [
        re.compile(r'^\s*CHAPTER\s+(?:TWO|2)\s*[:.]?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:TWO|2)\s*[:.]?\s+\w', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:TWO|2)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*2\.0\s+(?:REVIEW|LITERATURE)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*2\.0\s+', re.MULTILINE),
        re.compile(r'^\s*LITERATURE\s+REVIEW\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*REVIEW\s+OF\s+(?:RELATED\s+)?LITERATURE\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter3": [
        re.compile(r'^\s*CHAPTER\s+(?:THREE|3)\s*[:.]?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:THREE|3)\s*[:.]?\s+\w', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:THREE|3)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*3\.0\s+(?:RESEARCH\s+)?METHODOLOGY\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*3\.0\s+', re.MULTILINE),
        re.compile(r'^\s*(?:RESEARCH\s+)?METHODOLOGY\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*MATERIALS?\s+AND\s+METHODS?\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter4": [
        re.compile(r'^\s*CHAPTER\s+(?:FOUR|4)\s*[:.]?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:FOUR|4)\s*[:.]?\s+\w', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:FOUR|4)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*4\.0\s+(?:PRESENTATION|RESULTS?|DATA)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*4\.0\s+', re.MULTILINE),
        re.compile(r'^\s*PRESENTATION\s+OF\s+RESULTS?\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*DATA\s+PRESENTATION\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*RESULTS?\s+AND\s+DISCUSSION\b', re.IGNORECASE | re.MULTILINE),
    ],
    "chapter5": [
        re.compile(r'^\s*CHAPTER\s+(?:FIVE|5)\s*[:.]?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:FIVE|5)\s*[:.]?\s+\w', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CHAPTER\s+(?:FIVE|5)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*5\.0\s+(?:DISCUSSION|SUMMARY|CONCLUSION)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*5\.0\s+', re.MULTILINE),
        re.compile(r'^\s*DISCUSSION\s+OF\s+FINDINGS?\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*SUMMARY\s*,?\s*CONCLUSION\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*SUMMARY\s+OF\s+(?:THE\s+)?(?:STUDY|FINDINGS?)\b', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*CONCLUSION\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*DISCUSSION\s*,?\s+CONCLUSION\s*,?\s+AND\s+RECOMMEND', re.IGNORECASE | re.MULTILINE),
    ],
    "references": [
        re.compile(r'^\s*REFERENCES?\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*BIBLIOGRAPHY\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*LIST\s+OF\s+REFERENCES?\b', re.IGNORECASE | re.MULTILINE),
    ],
}

# Content signals for fallback detection
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
        "analysis of data", "empirical findings",
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

def _find_all_headings(
    text: str,
    toc_start: int = -1,
    toc_end: int = -1,
) -> List[Tuple[str, int, str]]:
    """
    Scan normalized text for section heading matches.

    CRITICAL: Skip matches inside the Table of Contents region.
    For each section key, we want the LAST match outside the TOC
    that produces the longest content, not the first (which may be in the TOC).

    Strategy: collect ALL matches, filter out TOC matches, then for each
    section key pick the match that produces the longest text span to the
    next heading.
    """
    all_matches: List[Tuple[str, int, str]] = []

    for section_key, patterns in _CHAPTER_PATTERNS.items():
        for pattern in patterns:
            for m in pattern.finditer(text):
                raw_pos = m.start()
                matched_text = m.group().strip()

                # Use the position of the first non-whitespace character
                # to avoid off-by-one issues at TOC boundaries.
                # Regex ^\s*CHAPTER can match the \n before the heading text.
                content_pos = raw_pos + len(m.group()) - len(m.group().lstrip())

                # SKIP matches inside the Table of Contents
                if toc_start >= 0 and toc_start <= content_pos < toc_end:
                    continue

                all_matches.append((section_key, raw_pos, matched_text))

    # Sort by position
    all_matches.sort(key=lambda x: x[1])

    # For each section key, we may have multiple matches (e.g., TOC + actual heading).
    # Group by section key and pick intelligently:
    # - If only one match: use it
    # - If multiple: pick the one that produces the largest text span
    from collections import defaultdict
    by_key: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    for key, pos, matched in all_matches:
        by_key[key].append((pos, matched))

    # Build all unique positions (for calculating spans)
    all_positions = sorted(set(pos for _, pos, _ in all_matches))
    all_positions.append(len(text))  # sentinel for last section

    def _span_for_pos(target_pos: int) -> int:
        """Calculate text span from target_pos to the next heading position."""
        for i, p in enumerate(all_positions):
            if p == target_pos:
                if i + 1 < len(all_positions):
                    return all_positions[i + 1] - target_pos
                return len(text) - target_pos
        return 0

    # Pick best match per section key
    result: List[Tuple[str, int, str]] = []
    for key in ALL_SECTION_KEYS:
        candidates = by_key.get(key, [])
        if not candidates:
            continue

        if len(candidates) == 1:
            pos, matched = candidates[0]
            result.append((key, pos, matched))
        else:
            # Pick the candidate with the largest span (= actual chapter, not TOC entry)
            best_pos, best_matched, best_span = candidates[0][0], candidates[0][1], 0
            for pos, matched in candidates:
                span = _span_for_pos(pos)
                if span > best_span:
                    best_pos, best_matched, best_span = pos, matched, span
            result.append((key, best_pos, best_matched))
            logger.info(
                f"  {key}: {len(candidates)} candidates, picked pos={best_pos} "
                f"(span={best_span} chars, text={best_matched!r})"
            )

    # Sort final result by position
    result.sort(key=lambda x: x[1])
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
    """
    logger.info("Running content-based fallback section detection...")
    text_lower = text.lower()
    result: Dict[str, str] = {k: "" for k in ALL_SECTION_KEYS}

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

        if signal_count >= 2 and best_pos < len(text):
            line_start = text_lower.rfind('\n', 0, best_pos)
            line_start = 0 if line_start == -1 else line_start + 1
            section_positions.append((section_key, line_start))

    if not section_positions:
        return result

    section_positions.sort(key=lambda x: x[1])

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
        confidence += 0.15

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
    Deterministic thesis section parser with TOC-awareness and multi-layer fallback.

    Layer 1: Regex heading detection (with TOC skip)
    Layer 2: Content-based keyword detection (fallback for messy DOCX)
    Layer 3: AI extraction fallback (safety net, temp=0)

    Same input → same output every time.
    """
    if not text or len(text.strip()) < 100:
        logger.warning("Document too short for section parsing")
        return {k: "" for k in ALL_SECTION_KEYS}

    normalized = _normalize_text(text)
    doc_length = len(normalized)
    logger.info(f"Section parsing: {doc_length} chars (normalized)")

    # ── Detect Table of Contents ──────────────────────────────────────────────
    toc_start, toc_end = _find_toc_boundaries(normalized)

    # ── Layer 1: Regex heading detection ──────────────────────────────────────
    headings = _find_all_headings(normalized, toc_start, toc_end)
    logger.info(f"Regex detected {len(headings)} headings: {[(k, m) for k, _, m in headings]}")

    result: Dict[str, str] = {}

    if headings:
        # Handle abstract
        first_chapter_pos = None
        for key, pos, _ in headings:
            if key.startswith("chapter"):
                first_chapter_pos = pos
                break

        has_abstract = any(k == "abstract" for k, _, _ in headings)
        if not has_abstract and first_chapter_pos and first_chapter_pos > 100:
            result["abstract"] = normalized[:first_chapter_pos].strip()
        else:
            result["abstract"] = _extract_section_text(normalized, headings, "abstract")

        for key in ["chapter1", "chapter2", "chapter3", "chapter4", "chapter5", "references"]:
            result[key] = _extract_section_text(normalized, headings, key)

    # Count found sections (above threshold)
    found_count = sum(
        1 for key in ALL_SECTION_KEYS
        if result.get(key, "") and len(result[key].strip()) >= MIN_SECTION_CHARS.get(key, 800)
    )

    # ── Layer 2: Content-based fallback ───────────────────────────────────────
    if found_count < 3 and doc_length > 5000:
        logger.warning(f"Regex found {found_count} sections in {doc_length}-char doc. Trying content fallback...")
        content_result = _content_based_split(normalized)
        content_found = sum(1 for v in content_result.values() if v)

        if content_found > found_count:
            for key in ALL_SECTION_KEYS:
                existing = result.get(key, "")
                min_chars = MIN_SECTION_CHARS.get(key, 800)
                if not existing or len(existing.strip()) < min_chars:
                    if content_result.get(key):
                        result[key] = content_result[key]

    # Recount
    final_count = sum(
        1 for key in ALL_SECTION_KEYS
        if result.get(key, "") and len(result[key].strip()) >= MIN_SECTION_CHARS.get(key, 800)
    )

    # ── Layer 3: AI fallback ──────────────────────────────────────────────────
    if final_count < 3 and doc_length > 5000:
        logger.warning(f"Only {final_count} sections found. AI fallback...")
        try:
            ai_result = _ai_extraction_fallback(normalized)
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
            logger.info(f"Section '{key}': {len(section_text.strip())} < {min_chars} → empty")
            result[key] = ""

    detected = [k for k, v in result.items() if v]
    missing = [k for k, v in result.items() if not v]
    logger.info(f"Final sections — detected: {detected}, missing: {missing}")

    return result


def _ai_extraction_fallback(text: str) -> Dict[str, str]:
    """Last-resort AI extraction (temp=0 for determinism)."""
    from .ai.router import get_router

    system_prompt = """Split this thesis into sections. Return ONLY JSON:
    {"abstract":"...","chapter1":"...","chapter2":"...","chapter3":"...","chapter4":"...","chapter5":"...","references":"..."}
    Extract FULL text per section. Empty string if not present. Do NOT summarize."""

    max_chars = 100000
    if len(text) > max_chars:
        text = text[:max_chars]

    router = get_router()
    result = router.generate(system_prompt, f"Thesis:\n{text}", task="extract_sections")
    result.pop("_meta", None)

    for key in ALL_SECTION_KEYS:
        if key not in result or result[key] is None:
            result[key] = ""

    return result


def get_extraction_confidences(text: str, sections: Dict[str, str]) -> Dict[str, float]:
    """Calculate extraction confidence for all sections."""
    normalized = _normalize_text(text)
    toc_start, toc_end = _find_toc_boundaries(normalized)
    headings = _find_all_headings(normalized, toc_start, toc_end)
    heading_keys = {k for k, _, _ in headings}

    return {
        key: _calculate_section_confidence(key, sections.get(key, ""), key in heading_keys)
        for key in ALL_SECTION_KEYS
    }
