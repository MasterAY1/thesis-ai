"""
Document Type Classifier
Detects whether an uploaded document is a:
- completed thesis
- proposal
- seminar
- dissertation

Used BEFORE grading starts to:
  1. Skip inapplicable sections (e.g., skip Chapter 4 for proposals)
  2. Adjust total obtainable score
  3. Prevent unfair deductions on proposals
"""
import re
import logging
from typing import Dict, Any

logger = logging.getLogger("thesis_ai.classifier")

# ── Signal definitions ─────────────────────────────────────────────────────────

PROPOSAL_PHRASES = [
    r"\bthis study intends to\b",
    r"\bwill be used\b",
    r"\bproposed study\b",
    r"\bwill be conducted\b",
    r"\bwill be administered\b",
    r"\bwill be collected\b",
    r"\bwill be analyzed\b",
    r"\bwill be recruited\b",
    r"\bwill be selected\b",
    r"\bit is hoped\b",
    r"\bthe researcher will\b",
    r"\bthis research proposal\b",
    r"\bresearch proposal\b",
    r"\bproposed research\b",
    r"\bintends to investigate\b",
    r"\bwill investigate\b",
    r"\bthe study will\b",
    r"\bplan to\b",
]

THESIS_PHRASES = [
    r"\bthe study found\b",
    r"\bthe results showed\b",
    r"\bthe findings revealed\b",
    r"\bdata were analyzed\b",
    r"\bdata was analyzed\b",
    r"\bthe study revealed\b",
    r"\bthis study found\b",
    r"\bthe respondents reported\b",
    r"\bresults indicated\b",
    r"\bfindings showed\b",
    r"\bit was found\b",
    r"\bthe analysis revealed\b",
    r"\bwas statistically significant\b",
    r"\btable \d+ shows\b",
    r"\bfigure \d+ shows\b",
]

CHAPTER4_SIGNALS = [
    r"\bchapter four\b",
    r"\bchapter 4\b",
    r"\bpresentation of result",
    r"\bdata presentation\b",
    r"\banalysis of data\b",
    r"\bresults and discussion\b",
]

CHAPTER5_SIGNALS = [
    r"\bchapter five\b",
    r"\bchapter 5\b",
    r"\bdiscussion of findings\b",
    r"\bsummary of findings\b",
    r"\bconclusion and recommendation",
    r"\bimplication.*findings\b",
]

SEMINAR_PHRASES = [
    r"\bseminar paper\b",
    r"\bseminar presentation\b",
    r"\bseminar report\b",
    r"\bthis seminar\b",
    r"\bin this seminar\b",
]

DISSERTATION_PHRASES = [
    r"\bdissertation\b",
    r"\bphd\b",
    r"\bdoctor of philosophy\b",
    r"\bpostgraduate dissertation\b",
]


def _count_matches(text: str, patterns: list) -> int:
    """Count how many patterns match in the text."""
    text_lower = text.lower()
    return sum(1 for p in patterns if re.search(p, text_lower))


def detect_document_type(text: str) -> Dict[str, Any]:
    """
    Analyses raw thesis text and classifies the document type.

    Returns:
        {
            "document_type": "proposal" | "thesis" | "seminar" | "dissertation",
            "confidence": 0.0 - 1.0,
            "reason": "Human-readable explanation",
            "skip_sections": ["chapter4", "chapter5"],  # sections to skip grading
            "adjusted_total": 65   # adjusted max marks (e.g., 100 - 35 for ch4+ch5)
        }
    """
    if not text or len(text.strip()) < 200:
        return {
            "document_type": "thesis",
            "confidence": 0.5,
            "reason": "Document too short to classify accurately.",
            "skip_sections": [],
            "adjusted_total": None,
        }

    text_lower = text.lower()
    word_count = len(text.split())

    # ── Count signal hits ──────────────────────────────────────────────────────
    proposal_hits   = _count_matches(text, PROPOSAL_PHRASES)
    thesis_hits     = _count_matches(text, THESIS_PHRASES)
    seminar_hits    = _count_matches(text, SEMINAR_PHRASES)
    dissert_hits    = _count_matches(text, DISSERTATION_PHRASES)
    ch4_present     = _count_matches(text, CHAPTER4_SIGNALS) > 0
    ch5_present     = _count_matches(text, CHAPTER5_SIGNALS) > 0

    # ── Future tense ratio ────────────────────────────────────────────────────
    future_verbs  = len(re.findall(r"\bwill\b", text_lower))
    past_verbs    = len(re.findall(r"\bwas\b|\bwere\b|\bfound\b|\bshowed\b|\brevealed\b|\banalyzed\b", text_lower))
    total_modals  = future_verbs + past_verbs + 1  # +1 avoids div-by-zero
    future_ratio  = future_verbs / total_modals

    logger.info(
        f"Classifier signals: proposal={proposal_hits}, thesis={thesis_hits}, "
        f"seminar={seminar_hits}, dissertation={dissert_hits}, "
        f"ch4={ch4_present}, ch5={ch5_present}, future_ratio={future_ratio:.2f}"
    )

    # ── Classification logic ──────────────────────────────────────────────────

    # Seminar check (highest specificity)
    if seminar_hits >= 2:
        return {
            "document_type": "seminar",
            "confidence": 0.85,
            "reason": "Document contains multiple seminar-specific phrases.",
            "skip_sections": ["chapter4", "chapter5"],
            "adjusted_total": 65,
        }

    # Dissertation check
    if dissert_hits >= 2 and word_count > 15000:
        return {
            "document_type": "dissertation",
            "confidence": 0.80,
            "reason": "Document identified as a dissertation-level research project.",
            "skip_sections": [],
            "adjusted_total": None,
        }

    # Proposal check — strong signals
    if proposal_hits >= 3 or (future_ratio > 0.55 and proposal_hits >= 1):
        skip = []
        skip_marks = 0
        reasons = []

        if not ch4_present:
            skip.append("chapter4")
            skip_marks += 15
            reasons.append("Chapter Four results are absent")
        if not ch5_present:
            skip.append("chapter5")
            skip_marks += 20
            reasons.append("Chapter Five findings are absent")

        reason = (
            f"Document appears to be a research proposal. "
            f"{', '.join(reasons) if reasons else 'Future tense dominates and proposal phrases found'}. "
            f"Proposal-specific sections will not be penalised."
        )
        return {
            "document_type": "proposal",
            "confidence": min(0.95, 0.60 + (proposal_hits * 0.05)),
            "reason": reason,
            "skip_sections": skip,
            "adjusted_total": 100 - skip_marks,
        }

    # Ambiguous proposal — moderate signals
    if proposal_hits >= 1 and future_ratio > 0.40 and not ch4_present:
        return {
            "document_type": "proposal",
            "confidence": 0.65,
            "reason": (
                "Document shows moderate proposal characteristics: "
                "future tense usage is elevated and Chapter Four data is missing."
            ),
            "skip_sections": ["chapter4"],
            "adjusted_total": 85,
        }

    # Default → completed thesis
    confidence = min(0.95, 0.55 + (thesis_hits * 0.05))
    if ch4_present:
        confidence = min(confidence + 0.10, 0.97)
    if ch5_present:
        confidence = min(confidence + 0.05, 0.97)

    return {
        "document_type": "thesis",
        "confidence": confidence,
        "reason": "Document contains empirical findings, results presentation, and past-tense reporting consistent with a completed thesis.",
        "skip_sections": [],
        "adjusted_total": None,
    }
