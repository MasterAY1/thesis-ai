"""
Deterministic Rule Engine — Pre-AI Checklist Validation (Institution-Aware)

Runs BEFORE the AI evaluation layer. Detects objective, verifiable issues
using regex, pattern matching, and structural analysis.

Rule checking is fully institution-aware:
  - Selectively executes rules based on active institution ("applies_to" registry).
  - Dynamically resolves section names and maximum marks from active rubric schema.
  - Dynamically formats reasoning to reference the selected school.
"""
import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("thesis_ai.rule_engine")

# ── Dynamic Section Metadata Resolver ───────────────────────────────────────────

def _get_section_meta(
    thesis_key: str,
    rubric: Optional[Dict[str, Any]],
    default_name: str,
    default_marks: int,
) -> tuple[str, int]:
    """
    Looks up section_name and max_marks dynamically from the active rubric.
    Falls back safely to defaults if rubric or mapping is missing.
    """
    if not rubric:
        return default_name, default_marks

    try:
        from .rubric_loader import get_section_mapping
        sec_map = get_section_mapping(rubric=rubric)
        if thesis_key in sec_map:
            sec_name = sec_map[thesis_key]
            sec_max = rubric.get("sections", {}).get(sec_name, {}).get("total", default_marks)
            return sec_name, sec_max
    except Exception as e:
        logger.warning(f"Error resolving section metadata for '{thesis_key}': {e}")

    return default_name, default_marks


# ── Issue builder ──────────────────────────────────────────────────────────────

def _make_issue(
    title: str,
    section: str,
    max_marks: int,
    deduction: int,
    reasoning: str,
    fix: str,
    severity: str = "medium",
    quote: str = "",
) -> Dict[str, Any]:
    """Build a standardized issue dict matching the AI output schema."""
    return {
        "issue_title": title,
        "severity": severity,
        "rubric": {
            "section": section,
            "max_marks": max_marks,
            "expected_requirement": f"{title} — {deduction} mark(s)",
        },
        "evidence": {
            "quote": quote[:200] if quote else "",
            "location": section,
        },
        "deduction_reasoning": reasoning,
        "supervisor_note": fix,
        "suggested_fix": fix,
        "recoverable_marks": deduction,
        "_source": "rule_engine",
    }


# ── Individual rule checks ─────────────────────────────────────────────────────

def check_abstract_keywords(text: str, rubric: Optional[Dict] = None) -> List[Dict]:
    """Check if abstract contains keywords (NMCN requires 4-6 keywords)."""
    issues = []
    text_lower = text.lower()
    
    section_name, max_marks = _get_section_meta("abstract", rubric, "Preliminary Pages", 8)
    
    # Look for a keywords line
    kw_match = re.search(r'key\s*words?\s*[:;]\s*(.+)', text_lower)
    
    if not kw_match:
        issues.append(_make_issue(
            title="Keywords Missing from Abstract",
            section=section_name,
            max_marks=max_marks,
            deduction=1,
            reasoning="The abstract does not contain a keywords line. The professional rubric expects 4-6 keywords.",
            fix="Add a 'Keywords:' line at the end of your abstract with 4-6 relevant terms.",
            severity="medium",
        ))
    else:
        # Count keywords (comma or semicolon separated)
        kw_text = kw_match.group(1).strip()
        keywords = [k.strip() for k in re.split(r'[,;]', kw_text) if k.strip()]
        if len(keywords) < 4:
            issues.append(_make_issue(
                title="Too Few Keywords",
                section=section_name,
                max_marks=max_marks,
                deduction=1,
                reasoning=f"Only {len(keywords)} keyword(s) found. The professional rubric expects 4-6 keywords.",
                fix=f"Add more keywords. You currently have {len(keywords)}, but the rubric expects 4-6.",
                severity="low",
                quote=kw_text[:100],
            ))

    return issues


def check_chapter1_structure(text: str, rubric: Optional[Dict] = None) -> List[Dict]:
    """Check Chapter One has required subsections."""
    issues = []
    text_lower = text.lower()
    
    section_name, max_marks = _get_section_meta("chapter1", rubric, "Chapter One", 15)
    
    required_subsections = [
        ("background", ["background to the study", "background of the study", "background", "1.1"], "Background to the Study", 3),
        ("problem", ["statement of problem", "statement of the problem", "problem statement", "1.2"], "Statement of Problem", 2),
        ("objectives", ["objectives of the study", "objective of the study", "research objectives", "aim of the study", "purpose of the study", "1.3"], "Objectives of the Study", 2),
        ("research_questions", ["research question", "research hypothesis", "hypothesis", "hypotheses", "1.4"], "Research Questions/Hypothesis", 2),
        ("significance", ["significance of the study", "significance", "1.5"], "Significance of the Study", 2),
        ("scope", ["scope of the study", "scope and limitation", "scope of study", "delimitation", "1.6"], "Scope of Study", 2),
        ("definitions", ["definition of terms", "operational definition", "1.7"], "Operational Definition of Terms", 2),
    ]
    
    for _, aliases, label, marks in required_subsections:
        found = any(alias in text_lower for alias in aliases)
        if not found:
            issues.append(_make_issue(
                title=f"{label} — Section Not Detected",
                section=section_name,
                max_marks=max_marks,
                deduction=min(marks, 2),  # Cap deterministic deduction at 2
                reasoning=f"The subsection '{label}' was not found in Chapter One. This is a required element.",
                fix=f"Add a clearly labeled '{label}' subsection to your Chapter One.",
                severity="high",
            ))

    return issues


def check_in_text_citations(text: str, rubric: Optional[Dict] = None) -> List[Dict]:
    """Check if Chapter Two uses in-text citations."""
    issues = []
    
    section_name, max_marks = _get_section_meta("chapter2", rubric, "Chapter Two", 15)
    
    # APA in-text citation patterns: (Author, 2020) or Author (2020)
    citation_count = len(re.findall(r'\([A-Z][a-z]+(?:\s+(?:et\s+al\.?|\&|and))?(?:,?\s+)?\d{4}\)', text))
    citation_count += len(re.findall(r'[A-Z][a-z]+\s+(?:et\s+al\.?\s+)?\(\d{4}\)', text))
    
    word_count = len(text.split())
    
    if word_count > 500 and citation_count < 3:
        issues.append(_make_issue(
            title="Insufficient In-Text Citations",
            section=section_name,
            max_marks=max_marks,
            deduction=1,
            reasoning=f"Only {citation_count} in-text citation(s) detected in a {word_count}-word literature review. This is insufficient.",
            fix="Add more in-text citations in APA format, e.g., (Author, 2020) or Author (2020).",
            severity="high",
        ))

    return issues


def check_chapter3_structure(text: str, rubric: Optional[Dict] = None) -> List[Dict]:
    """Check Chapter Three has required methodology subsections."""
    issues = []
    text_lower = text.lower()
    
    section_name, max_marks = _get_section_meta("chapter3", rubric, "Chapter Three", 20)
    inst_name = rubric.get("institution_name", "the University") if rubric else "the University"
    
    required = [
        (["research design", "study design"], "Research Design", 1),
        (["setting", "study area", "study setting", "study location"], "Setting", 2),
        (["target population", "study population", "population of the study"], "Target Population", 1),
        (["sample size", "sampling size"], "Sampling Size", 1),
        (["sampling technique", "sampling method", "sampling procedure"], "Sampling Technique", 3),
        (["instrument", "data collection instrument", "questionnaire", "tool for data collection"], "Instruments for Data Collection", 1),
        (["validity", "face validity", "content validity"], "Validity of Instrument", 1),
        (["reliability", "reliability index", "cronbach", "test-retest"], "Reliability of Instrument", 3),
        (["method of data collection", "data collection method", "procedure for data collection", "administration of instrument"], "Method of Data Collection", 3),
        (["method of data analysis", "data analysis", "statistical analysis", "spss", "chi-square", "t-test", "anova"], "Method of Data Analysis", 2),
        (["ethical consideration", "ethical approval", "informed consent", "ethical clearance"], "Ethical Consideration", 2),
    ]
    
    for aliases, label, marks in required:
        found = any(alias in text_lower for alias in aliases)
        if not found:
            issues.append(_make_issue(
                title=f"{label} — Not Detected in Methodology",
                section=section_name,
                max_marks=max_marks,
                deduction=min(marks, 2),
                reasoning=f"'{label}' was not found in Chapter Three. This is required by {inst_name} guidelines.",
                fix=f"Add a clearly labeled '{label}' subsection to your Chapter Three.",
                severity="high" if marks >= 2 else "medium",
            ))

    return issues


def check_chapter4_tables(text: str, rubric: Optional[Dict] = None) -> List[Dict]:
    """Check Chapter Four has tables/figures for data presentation."""
    issues = []
    text_lower = text.lower()
    
    section_name, max_marks = _get_section_meta("chapter4", rubric, "Chapter Four", 15)
    inst_name = rubric.get("institution_name", "the University") if rubric else "the University"
    
    # Count tables
    table_count = len(re.findall(r'\btable\s+\d+', text_lower))
    figure_count = len(re.findall(r'\bfig(?:ure)?\s+\d+', text_lower))
    
    if table_count == 0 and figure_count == 0:
        issues.append(_make_issue(
            title="No Tables or Figures Detected",
            section=section_name,
            max_marks=max_marks,
            deduction=4,
            reasoning=f"No tables or figures were found in Chapter Four. {inst_name} guidelines require data presentation using tables and figures.",
            fix="Add numbered tables (Table 1, Table 2…) and/or figures to present your results.",
            severity="high",
        ))
    elif table_count < 2:
        issues.append(_make_issue(
            title="Insufficient Tables for Data Presentation",
            section=section_name,
            max_marks=max_marks,
            deduction=2,
            reasoning=f"Only {table_count} table(s) found. Most research projects require multiple tables to present results adequately.",
            fix="Add more tables to present your research findings comprehensively.",
            severity="medium",
        ))

    return issues


def check_chapter5_structure(text: str, rubric: Optional[Dict] = None) -> List[Dict]:
    """Check Chapter Five has required discussion subsections."""
    issues = []
    text_lower = text.lower()
    
    section_name, max_marks = _get_section_meta("chapter5", rubric, "Chapter Five", 15)
    
    required = [
        (["summary", "summary of the study", "summary of findings"], "Summary", 2),
        (["conclusion"], "Conclusion", 2),
        (["recommendation"], "Recommendations", 3),
        (["limitation", "delimitation"], "Limitations of the Study", 1),
        (["suggestion for further", "areas for further", "suggestion for future"], "Suggestions for Further Studies", 1),
    ]
    
    for aliases, label, marks in required:
        found = any(alias in text_lower for alias in aliases)
        if not found:
            issues.append(_make_issue(
                title=f"{label} — Not Detected in Chapter Five",
                section=section_name,
                max_marks=max_marks,
                deduction=min(marks, 2),
                reasoning=f"'{label}' subsection was not found in Chapter Five.",
                fix=f"Add a '{label}' subsection to your Chapter Five.",
                severity="high" if marks >= 2 else "medium",
            ))

    return issues


def check_references_format(text: str, rubric: Optional[Dict] = None) -> List[Dict]:
    """Check references section for APA formatting signals."""
    issues = []
    text_lower = text.lower()
    
    section_name, max_marks = _get_section_meta("references", rubric, "References and Appendix", 7)
    
    # Count reference entries (lines starting with author-like patterns)
    ref_lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 30]
    
    if len(ref_lines) < 5:
        issues.append(_make_issue(
            title="Very Few References",
            section=section_name,
            max_marks=max_marks,
            deduction=2,
            reasoning=f"Only {len(ref_lines)} reference entries detected. A thesis typically needs 15+ references.",
            fix="Add more references from peer-reviewed journals and textbooks to support your study.",
            severity="high",
        ))
    
    # APA format checks
    # Check for year in parentheses pattern: Author (2020)
    apa_year_pattern = len(re.findall(r'\(\d{4}\)', text))
    if apa_year_pattern < 3 and len(ref_lines) > 5:
        issues.append(_make_issue(
            title="APA Formatting Not Detected",
            section=section_name,
            max_marks=max_marks,
            deduction=2,
            reasoning="References do not appear to follow APA format. Year-in-parentheses pattern not found consistently.",
            fix="Format all references using APA 7th Edition style. Example: Author, A. B. (2020). Title of article. Journal Name, 10(2), 1-15.",
            severity="high",
        ))
    
    # Check alphabetical ordering (first letters of non-empty lines)
    first_chars = []
    for line in ref_lines:
        if line and line[0].isalpha():
            first_chars.append(line[0].upper())
    
    if len(first_chars) >= 5:
        # Check if roughly alphabetical
        sorted_chars = sorted(first_chars)
        mismatches = sum(1 for a, b in zip(first_chars, sorted_chars) if a != b)
        if mismatches > len(first_chars) * 0.4:
            issues.append(_make_issue(
                title="References Not Alphabetically Arranged",
                section=section_name,
                max_marks=max_marks,
                deduction=1,
                reasoning="References do not appear to be arranged alphabetically by author surname.",
                fix="Arrange all your references in alphabetical order by the first author's surname.",
                severity="medium",
            ))

    return issues


def check_reference_currency(
    text: str,
    chapter2_text: str = "",
    rubric: Optional[Dict] = None,
) -> List[Dict]:
    """Check if references are current (within last 10 years for books, 5 for journals)."""
    issues = []
    combined = text + " " + chapter2_text
    
    section_name, max_marks = _get_section_meta("references", rubric, "References and Appendix", 7)
    inst_name = rubric.get("institution_name", "the University") if rubric else "the University"
    
    # Extract all years from references
    years = [int(y) for y in re.findall(r'\(((?:19|20)\d{2})\)', combined)]
    
    if not years:
        return issues
    
    current_year = 2026
    old_refs = [y for y in years if current_year - y > 10]
    recent_refs = [y for y in years if current_year - y <= 5]
    
    total = len(years)
    if total > 0:
        old_ratio = len(old_refs) / total
        if old_ratio > 0.5:
            issues.append(_make_issue(
                title="Majority of References Are Outdated",
                section=section_name,
                max_marks=max_marks,
                deduction=2,
                reasoning=f"{len(old_refs)} of {total} references are older than 10 years ({round(old_ratio*100)}%). {inst_name} guidelines expect current sources.",
                fix="Replace older references with recent publications (journals within 5 years, books within 10 years).",
                severity="high",
            ))
        elif old_ratio > 0.3:
            issues.append(_make_issue(
                title="Many References Are Not Current",
                section=section_name,
                max_marks=max_marks,
                deduction=1,
                reasoning=f"{len(old_refs)} of {total} references are older than 10 years. Consider updating with more recent sources.",
                fix="Add more recent references, especially peer-reviewed journal articles from the last 5 years.",
                severity="medium",
            ))

    return issues


# ── Rule Registry ──────────────────────────────────────────────────────────────

ALL_KNOWN_INSTITUTIONS = [
    "nmcn", "nigeria_general", "lasu", "unilag", "oau", "futa",
    "ui", "unn", "abu", "covenant", "babcock", "futo", "uniben", "unizik", "adaptive"
]

RULE_REGISTRY = [
    {
        "rule": "abstract_keywords",
        "applies_to": ["nmcn"],  # Keywords check is NMCN specific
        "check_func": lambda s, r: check_abstract_keywords(s.get("abstract", ""), rubric=r)
    },
    {
        "rule": "chapter1_structure",
        "applies_to": ALL_KNOWN_INSTITUTIONS,
        "check_func": lambda s, r: check_chapter1_structure(s.get("chapter1", ""), rubric=r)
    },
    {
        "rule": "in_text_citations",
        "applies_to": ALL_KNOWN_INSTITUTIONS,
        "check_func": lambda s, r: check_in_text_citations(s.get("chapter2", ""), rubric=r)
    },
    {
        "rule": "chapter3_structure",
        "applies_to": ALL_KNOWN_INSTITUTIONS,
        "check_func": lambda s, r: check_chapter3_structure(s.get("chapter3", ""), rubric=r)
    },
    {
        "rule": "chapter4_tables",
        "applies_to": ALL_KNOWN_INSTITUTIONS,
        "check_func": lambda s, r: check_chapter4_tables(s.get("chapter4", ""), rubric=r)
    },
    {
        "rule": "chapter5_structure",
        "applies_to": ALL_KNOWN_INSTITUTIONS,
        "check_func": lambda s, r: check_chapter5_structure(s.get("chapter5", ""), rubric=r)
    },
    {
        "rule": "references_format",
        "applies_to": ALL_KNOWN_INSTITUTIONS,
        "check_func": lambda s, r: check_references_format(s.get("references", ""), rubric=r)
    },
    {
        "rule": "reference_currency",
        "applies_to": ALL_KNOWN_INSTITUTIONS,
        "check_func": lambda s, r: check_reference_currency(s.get("references", ""), s.get("chapter2", ""), rubric=r)
    }
]


# ── Main entry point ───────────────────────────────────────────────────────────

def run_rule_checks(
    sections: Dict[str, str],
    institution: str = "nmcn",
    rubric: Optional[Dict] = None,
) -> List[Dict]:
    """
    Run ALL deterministic rule checks against extracted sections.
    Selects and executes only the rules permitted for the active institution.
    Dynamically maps section name & max marks from active rubric schema.

    No AI calls. No randomness. Fully deterministic.
    """
    all_issues: List[Dict] = []
    inst_code = institution.lower() if institution else "nmcn"
    
    logger.info(f"Running checklist rules registry for '{inst_code}'")

    for entry in RULE_REGISTRY:
        if inst_code not in entry["applies_to"]:
            logger.info(f"Skipping rule '{entry['rule']}' for institution '{inst_code}'")
            continue
            
        try:
            issues = entry["check_func"](sections, rubric)
            all_issues.extend(issues)
        except Exception as e:
            logger.error(f"Error running rule check '{entry['rule']}': {e}", exc_info=True)
            
    logger.info(f"Rule engine completed: {len(all_issues)} deterministic issues found")
    return all_issues
