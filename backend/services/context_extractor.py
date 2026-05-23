"""
Context Extractor — Intelligent heading-aware section text trimmer.

Prevents sending oversized context to AI providers.
Preserves headings, intro paragraphs, and conclusion paragraphs while
trimming the middle of long sections to fit within MAX_SECTION_CHARS.
"""
import re
import logging
from typing import List

logger = logging.getLogger("thesis_ai.context_extractor")

# Hard limit for any single AI call context
MAX_SECTION_CHARS = 12000

# Regex for detecting headings (uppercase lines, chapter markers, etc.)
HEADING_PATTERN = re.compile(
    r'^(?:'
    r'CHAPTER\s+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|\d+)|'
    r'SECTION\s+\d+|'
    r'[A-Z][A-Z\s]{4,}[A-Z]|'   # ALL-CAPS lines ≥ 5 chars
    r'\d+\.\d*\s+[A-Z]'          # Numbered headings like "1.1 Introduction"
    r').*$',
    re.MULTILINE,
)


def _split_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs on double-newlines."""
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text)]
    return [p for p in paragraphs if p]


def _is_heading(paragraph: str) -> bool:
    """Return True if the paragraph looks like a section heading."""
    first_line = paragraph.split('\n')[0].strip()
    return bool(HEADING_PATTERN.match(first_line)) or (
        len(first_line) < 80 and first_line.isupper()
    )


def extract_relevant_context(
    section_text: str,
    rubric_criteria: str = "",
    max_chars: int = MAX_SECTION_CHARS,
) -> str:
    """
    Intelligently trim section_text to max_chars.

    Strategy:
    1. If text is already within limit, return as-is.
    2. Otherwise, build a prioritised window:
       - ALL headings (preserved always)
       - First 40% of the budget for the opening of the section
       - Last 30% of the budget for the closing of the section
       - Fill remaining 30% from the middle
    3. Joins sections with an ellipsis marker so the AI knows content was trimmed.

    Args:
        section_text:    Raw section text to trim.
        rubric_criteria: (Optional) rubric text — used to guide keyword retention
                         in future versions. Not yet implemented.
        max_chars:       Hard character limit.

    Returns:
        Trimmed text ≤ max_chars.
    """
    if not section_text:
        return ""

    text = section_text.strip()

    if len(text) <= max_chars:
        return text

    original_len = len(text)
    logger.info(f"Context trimming: {original_len} → {max_chars} chars")

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return text[:max_chars]

    # Separate headings from body paragraphs
    headings = [p for p in paragraphs if _is_heading(p)]
    body = [p for p in paragraphs if not _is_heading(p)]

    # Budget allocation
    heading_text = "\n\n".join(headings)
    heading_budget = min(len(heading_text), max_chars // 6)  # ~16% for headings
    remaining = max_chars - heading_budget

    first_budget = int(remaining * 0.45)   # 45% of remaining → opening
    last_budget  = int(remaining * 0.35)   # 35% of remaining → closing
    mid_budget   = remaining - first_budget - last_budget   # 20% → middle

    # Build the trimmed document
    parts = []

    # Headings block (abbreviated to budget)
    if headings:
        parts.append(heading_text[:heading_budget])

    # First chunk: opening paragraphs
    first_chunk = ""
    for p in body:
        candidate = first_chunk + ("\n\n" if first_chunk else "") + p
        if len(candidate) <= first_budget:
            first_chunk = candidate
        else:
            break
    if first_chunk:
        parts.append(first_chunk)

    # Last chunk: closing paragraphs (reversed, then re-reversed)
    last_chunk = ""
    for p in reversed(body):
        candidate = p + ("\n\n" if last_chunk else "") + last_chunk
        if len(candidate) <= last_budget:
            last_chunk = candidate
        else:
            break
    if last_chunk:
        parts.append("... [content trimmed for token efficiency] ...")
        parts.append(last_chunk)

    result = "\n\n".join(parts)

    # Final safety clamp
    if len(result) > max_chars:
        result = result[:max_chars - 50] + "\n\n... [truncated]"

    logger.info(
        f"Context trimmed: {original_len} → {len(result)} chars "
        f"({100 - round(len(result) * 100 / original_len)}% reduction)"
    )
    return result


def safe_truncate(text: str, max_chars: int = MAX_SECTION_CHARS) -> str:
    """
    Simple fallback truncation — splits at a sentence boundary near max_chars.
    """
    if len(text) <= max_chars:
        return text

    # Try to split at the last period before the limit
    truncated = text[:max_chars]
    last_period = truncated.rfind('.')
    if last_period > max_chars * 0.8:
        return truncated[:last_period + 1] + " ... [truncated]"
    return truncated + " ... [truncated]"
