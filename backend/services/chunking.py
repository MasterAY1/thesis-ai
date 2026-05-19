"""
Document Chunking Service — Splits large text into manageable chunks for AI processing.

Ensures that:
- No single AI call receives more text than it can handle
- GitHub GPT never receives the entire thesis at once
- Section boundaries are respected during chunk merging
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger("thesis_ai.chunking")

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
DEFAULT_CHUNK_SIZE = 4000    # characters per chunk
DEFAULT_OVERLAP = 500        # overlap between chunks for context continuity

# Token estimation: ~4 chars per token (conservative for English)
CHARS_PER_TOKEN = 4

# GitHub GPT safety limits
GITHUB_MAX_TOKENS = 8000
GITHUB_SAFE_TOKENS = 6000   # hard cap to stay safely under 8k
GITHUB_MAX_CHARS = GITHUB_SAFE_TOKENS * CHARS_PER_TOKEN  # 24,000 chars


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    return len(text) // CHARS_PER_TOKEN


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: The raw text to split.
        chunk_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.

    Returns:
        A list of text chunks.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # If the text is small enough, return as a single chunk
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary (period, newline) if possible
        if end < len(text):
            # Look for a natural break point in the last 200 chars of the chunk
            search_start = max(start, end - 200)
            last_period = text.rfind(".", search_start, end)
            last_newline = text.rfind("\n", search_start, end)
            break_point = max(last_period, last_newline)

            if break_point > search_start:
                end = break_point + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward (accounting for overlap)
        start = end - overlap
        if start <= 0 and end >= len(text):
            break

    logger.info(f"Chunked {len(text)} chars into {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
    return chunks


def merge_section_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge AI results from multiple chunks into a single consolidated result.

    Combines issues lists and deduplicates by issue_title.
    """
    all_issues = []
    seen_titles = set()

    for result in results:
        if "error" in result:
            continue
        for issue in result.get("issues", []):
            title = issue.get("issue_title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_issues.append(issue)

    return {"issues": all_issues}


def safe_truncate_for_github(text: str, max_chars: int = GITHUB_MAX_CHARS) -> str:
    """
    Safely truncate text to fit within GitHub GPT's token limits.

    If the text exceeds the safe limit, it keeps the first and last portions
    and inserts a truncation notice.
    """
    if len(text) <= max_chars:
        return text

    estimated_tokens = estimate_tokens(text)
    logger.warning(
        f"Text too large for GitHub GPT: {len(text)} chars (~{estimated_tokens} tokens). "
        f"Truncating to {max_chars} chars (~{max_chars // CHARS_PER_TOKEN} tokens)."
    )

    # Keep the beginning and end (they usually contain the most important structural info)
    first_portion = max_chars * 2 // 3
    last_portion = max_chars // 3

    return (
        text[:first_portion]
        + "\n\n... [CONTENT TRUNCATED FOR TOKEN SAFETY] ...\n\n"
        + text[-last_portion:]
    )


def summarize_for_github(text: str, max_chars: int = GITHUB_MAX_CHARS) -> str:
    """
    Create a condensed version of text suitable for GitHub GPT.

    Strategy:
    1. If under limit, return as-is
    2. If over limit, extract key sentences (first + last of each paragraph)
    """
    if len(text) <= max_chars:
        return text

    paragraphs = text.split("\n\n")
    condensed = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        sentences = para.split(". ")
        if len(sentences) <= 2:
            condensed.append(para)
        else:
            # Keep first and last sentence of each paragraph
            condensed.append(f"{sentences[0]}. ... {sentences[-1]}")

    result = "\n\n".join(condensed)

    # If still too long, hard truncate
    if len(result) > max_chars:
        result = safe_truncate_for_github(result, max_chars)

    logger.info(f"Summarized {len(text)} chars -> {len(result)} chars for GitHub GPT")
    return result
