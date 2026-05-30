"""
Modular Rubric Loader — Multi-Institution Architecture

Supports:
  1. Official rubrics (rubrics/<code>/rubric.json)         — NMCN
  2. Institutional rubrics (rubrics/institutions/<code>/)   — LASU, UNILAG, etc.
  3. General fallback (rubrics/nigeria_general/)            — default for unknown institutions
  4. Rubric inheritance: {"extends": "nigeria_general", "overrides": {...}}
  5. Runtime adaptive rubrics (in-memory, never persisted)

Lookup order:
  rubrics/<code>/ → rubrics/institutions/<code>/ → rubrics/nigeria_general/

CRITICAL: NMCN rubric is NEVER modified. It's loaded directly from its own folder.
"""
import copy
import json
import os
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("thesis_ai.rubric_loader")

RUBRICS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rubrics")

# ── Registry of known institutions ─────────────────────────────────────────────
# Type: "official" (fixed engine), "institutional" (school-specific), "general" (fallback)
INSTITUTION_REGISTRY = [
    {"code": "nmcn",            "name": "Nursing & Midwifery Council of Nigeria", "type": "official"},
    {"code": "nigeria_general", "name": "General Nigerian University",            "type": "general"},
    {"code": "lasu",            "name": "Lagos State University",                 "type": "institutional"},
    {"code": "unilag",          "name": "University of Lagos",                    "type": "institutional"},
    {"code": "oau",             "name": "Obafemi Awolowo University",             "type": "institutional"},
    {"code": "futa",            "name": "Federal University of Technology, Akure","type": "institutional"},
    {"code": "ui",              "name": "University of Ibadan",                   "type": "institutional"},
    {"code": "unn",             "name": "University of Nigeria, Nsukka",          "type": "institutional"},
    {"code": "abu",             "name": "Ahmadu Bello University",                "type": "institutional"},
    {"code": "covenant",        "name": "Covenant University",                    "type": "institutional"},
    {"code": "babcock",         "name": "Babcock University",                     "type": "institutional"},
    {"code": "futo",            "name": "Federal University of Technology, Owerri","type": "institutional"},
    {"code": "uniben",          "name": "University of Benin",                    "type": "institutional"},
    {"code": "unizik",          "name": "Nnamdi Azikiwe University",              "type": "institutional"},
]


# ── Cascading rubric lookup ───────────────────────────────────────────────────

def _find_rubric_path(institution: str) -> Optional[str]:
    """
    Find the rubric JSON file using cascading lookup:
      1. rubrics/<institution>/rubric.json        (official: NMCN)
      2. rubrics/institutions/<institution>/rubric.json  (institutional)
      3. rubrics/nigeria_general/rubric.json       (fallback)
    Returns the first path found, or None.
    """
    paths = [
        os.path.join(RUBRICS_DIR, institution, "rubric.json"),
        os.path.join(RUBRICS_DIR, "institutions", institution, "rubric.json"),
    ]

    for path in paths:
        if os.path.exists(path):
            return path

    # Fallback to nigeria_general
    fallback = os.path.join(RUBRICS_DIR, "nigeria_general", "rubric.json")
    if os.path.exists(fallback):
        logger.info(f"Rubric for '{institution}' not found, falling back to nigeria_general")
        return fallback

    return None


def _load_raw_rubric(path: str) -> Dict[str, Any]:
    """Load a rubric JSON file from disk."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_inheritance(rubric: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve rubric inheritance.

    If a rubric has {"extends": "nigeria_general", "overrides": {...}},
    load the parent rubric and merge overrides on top.

    Inheritance only goes 1 level deep (no chains).
    """
    parent_code = rubric.get("extends")
    if not parent_code:
        return rubric

    # Load parent rubric
    parent_path = _find_rubric_path(parent_code)
    if not parent_path:
        logger.warning(f"Parent rubric '{parent_code}' not found, using child as-is")
        return rubric

    parent = _load_raw_rubric(parent_path)

    # If the parent also extends, resolve it first (1 level only)
    if parent.get("extends"):
        parent = _resolve_inheritance(parent)

    # Deep merge: start with parent, apply child overrides
    merged = copy.deepcopy(parent)

    # Override top-level metadata
    merged["institution_name"] = rubric.get("institution_name", parent.get("institution_name", ""))
    merged["institution_code"] = rubric.get("institution_code", parent.get("institution_code", ""))

    # Apply section overrides
    overrides = rubric.get("overrides", {})
    if overrides and "sections" not in overrides:
        # Simple format: {"chapter_three": {"marks": 25}}
        # Convert thesis_key-based overrides to section-name-based
        for section_name, section_data in merged.get("sections", {}).items():
            thesis_key = section_data.get("thesis_key")
            if thesis_key and thesis_key in overrides:
                override = overrides[thesis_key]
                if "marks" in override:
                    section_data["total"] = override["marks"]
                if "criteria" in override:
                    section_data["criteria"] = override["criteria"]
    elif overrides:
        # Full section overrides
        for section_name, override in overrides.get("sections", {}).items():
            if section_name in merged.get("sections", {}):
                if isinstance(override, dict):
                    merged["sections"][section_name].update(override)

    # Recalculate total_marks
    merged["total_marks"] = sum(
        s.get("total", 0) for s in merged.get("sections", {}).values()
    )

    return merged


# ── Public API ─────────────────────────────────────────────────────────────────

def list_available_rubrics() -> List[str]:
    """Returns a list of all available institution codes."""
    codes = set()

    # Scan rubrics/ top-level (official rubrics like NMCN)
    if os.path.exists(RUBRICS_DIR):
        for d in os.listdir(RUBRICS_DIR):
            rubric_file = os.path.join(RUBRICS_DIR, d, "rubric.json")
            if os.path.isdir(os.path.join(RUBRICS_DIR, d)) and os.path.exists(rubric_file):
                codes.add(d)

    # Scan rubrics/institutions/
    inst_dir = os.path.join(RUBRICS_DIR, "institutions")
    if os.path.exists(inst_dir):
        for d in os.listdir(inst_dir):
            rubric_file = os.path.join(inst_dir, d, "rubric.json")
            if os.path.isdir(os.path.join(inst_dir, d)) and os.path.exists(rubric_file):
                codes.add(d)

    return sorted(codes)


def list_all_institutions() -> List[Dict[str, str]]:
    """
    Returns enriched institution list for the frontend dropdown.
    Each entry: {"code", "name", "type"}
    """
    available = set(list_available_rubrics())
    result = []

    for inst in INSTITUTION_REGISTRY:
        if inst["code"] in available:
            result.append(dict(inst))

    # Add any on-disk institutions not in registry
    for code in available:
        if not any(i["code"] == code for i in result):
            result.append({
                "code": code,
                "name": code.upper(),
                "type": "institutional",
            })

    return result


def load_rubric(institution: str = "nmcn") -> Dict[str, Any]:
    """
    Loads the full rubric config for an institution.
    Uses cascading lookup and resolves inheritance.
    """
    rubric_path = _find_rubric_path(institution)
    if not rubric_path:
        raise FileNotFoundError(
            f"Rubric not found for institution: {institution}. "
            f"Available: {list_available_rubrics()}"
        )

    rubric = _load_raw_rubric(rubric_path)
    resolved = _resolve_inheritance(rubric)

    logger.debug(
        f"Loaded rubric: {resolved.get('institution_name', institution)} "
        f"({resolved.get('total_marks', '?')} marks, "
        f"{len(resolved.get('sections', {}))} sections)"
    )
    return resolved


def load_rubric_with_override(
    institution: str = "nmcn",
    custom_rubric: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Load a rubric with optional in-memory adaptive override.

    If custom_rubric is provided, it's used directly (after validation).
    Otherwise, loads from disk using cascading lookup.

    The custom_rubric is NEVER persisted to disk.
    """
    if custom_rubric is not None:
        # Validate basic structure
        if not isinstance(custom_rubric, dict) or "sections" not in custom_rubric:
            logger.warning("Invalid custom_rubric structure, falling back to institution rubric")
            return load_rubric(institution)

        # Ensure total_marks is set
        if "total_marks" not in custom_rubric:
            custom_rubric["total_marks"] = sum(
                s.get("total", 0)
                for s in custom_rubric.get("sections", {}).values()
            )

        custom_rubric.setdefault("institution_name", "Custom Adaptive Rubric")
        custom_rubric.setdefault("institution_code", "adaptive")
        return custom_rubric

    return load_rubric(institution)


def get_rubric_for_section(
    section_name: str,
    institution: str = "nmcn",
    rubric: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Returns rubric metadata for a specific section only.
    Accepts either an institution code or a pre-loaded rubric dict.
    """
    if rubric is None:
        rubric = load_rubric(institution)

    sections = rubric.get("sections", {})

    # Direct match
    if section_name in sections:
        return {
            "section_name": section_name,
            "max_marks": sections[section_name]["total"],
            "criteria": sections[section_name]["criteria"],
            "thesis_key": sections[section_name].get("thesis_key"),
        }

    # Fuzzy match (e.g., "chapter3" -> "Chapter Three")
    for key, data in sections.items():
        if key.lower().replace(" ", "") in section_name.lower().replace(" ", ""):
            return {
                "section_name": key,
                "max_marks": data["total"],
                "criteria": data["criteria"],
                "thesis_key": data.get("thesis_key"),
            }

    return None


def get_flat_rubric(
    institution: str = "nmcn",
    rubric: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """Returns a flat section_name -> max_marks map for the scoring engine."""
    if rubric is None:
        rubric = load_rubric(institution)
    flat = {name: data["total"] for name, data in rubric["sections"].items()}
    flat["General"] = 0
    return flat


def build_section_prompt(
    section_name: str,
    institution: str = "nmcn",
    rubric: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Builds a human-readable rubric prompt for ONE section only.
    This is injected into the AI prompt when evaluating that specific section.
    """
    section_data = get_rubric_for_section(section_name, institution, rubric)
    if not section_data:
        return f"No rubric criteria found for section: {section_name}"

    lines = [f"RUBRIC FOR {section_data['section_name'].upper()} (Total: {section_data['max_marks']} marks):"]
    for criterion, marks in section_data["criteria"].items():
        lines.append(f"  - {criterion}: {marks} mark(s)")
    return "\n".join(lines)


def get_section_mapping(
    institution: str = "nmcn",
    rubric: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Returns a mapping of thesis_key -> section_name.
    e.g., {"abstract": "Preliminary Pages", "chapter1": "Chapter One", ...}
    """
    if rubric is None:
        rubric = load_rubric(institution)
    mapping = {}
    for name, data in rubric["sections"].items():
        key = data.get("thesis_key")
        if key:
            mapping[key] = name
    return mapping


def get_institution_name(
    institution: str = "nmcn",
    rubric: Optional[Dict[str, Any]] = None,
) -> str:
    """Returns the human-readable institution name for prompts and UI."""
    if rubric is not None:
        return rubric.get("institution_name", institution.upper())

    try:
        r = load_rubric(institution)
        return r.get("institution_name", institution.upper())
    except FileNotFoundError:
        return institution.upper()


def get_rubric_metadata(
    institution: str = "nmcn",
    rubric: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns rubric summary for the preview modal.
    Frontend uses this to show extracted rubric structure before evaluation.
    """
    if rubric is None:
        rubric = load_rubric(institution)

    sections_summary = []
    for name, data in rubric.get("sections", {}).items():
        sections_summary.append({
            "name": name,
            "total": data.get("total", 0),
            "thesis_key": data.get("thesis_key"),
            "criteria_count": len(data.get("criteria", {})),
            "criteria": data.get("criteria", {}),
        })

    return {
        "institution_name": rubric.get("institution_name", ""),
        "institution_code": rubric.get("institution_code", ""),
        "total_marks": rubric.get("total_marks", 0),
        "section_count": len(sections_summary),
        "sections": sections_summary,
    }
