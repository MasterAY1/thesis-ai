"""
Modular Rubric Loader
Loads rubric configurations from JSON files, enabling multi-institution support.
To add a new institution, simply create: rubrics/<institution_code>/rubric.json
"""
import json
import os
from typing import Dict, Any, Optional, List

RUBRICS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rubrics")

def list_available_rubrics() -> List[str]:
    """Returns a list of all available institution codes."""
    if not os.path.exists(RUBRICS_DIR):
        return []
    return [d for d in os.listdir(RUBRICS_DIR)
            if os.path.isdir(os.path.join(RUBRICS_DIR, d))
            and os.path.exists(os.path.join(RUBRICS_DIR, d, "rubric.json"))]

def load_rubric(institution: str = "nmcn") -> Dict[str, Any]:
    """Loads the full rubric config for an institution."""
    rubric_path = os.path.join(RUBRICS_DIR, institution, "rubric.json")
    if not os.path.exists(rubric_path):
        raise FileNotFoundError(f"Rubric not found for institution: {institution}")
    with open(rubric_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_rubric_for_section(section_name: str, institution: str = "nmcn") -> Optional[Dict[str, Any]]:
    """
    Returns rubric metadata for a specific section only.
    This is the core function that enables section-aware evaluation — 
    only the relevant criteria are loaded and injected into the AI prompt.
    """
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

def get_flat_rubric(institution: str = "nmcn") -> Dict[str, int]:
    """Returns a flat section_name -> max_marks map for the scoring engine."""
    rubric = load_rubric(institution)
    flat = {name: data["total"] for name, data in rubric["sections"].items()}
    flat["General"] = 0
    return flat

def build_section_prompt(section_name: str, institution: str = "nmcn") -> str:
    """
    Builds a human-readable rubric prompt for ONE section only.
    This is injected into the AI prompt when evaluating that specific section.
    """
    section_data = get_rubric_for_section(section_name, institution)
    if not section_data:
        return f"No rubric criteria found for section: {section_name}"
    
    lines = [f"RUBRIC FOR {section_data['section_name'].upper()} (Total: {section_data['max_marks']} marks):"]
    for criterion, marks in section_data["criteria"].items():
        lines.append(f"  - {criterion}: {marks} mark(s)")
    return "\n".join(lines)

def get_section_mapping(institution: str = "nmcn") -> Dict[str, str]:
    """
    Returns a mapping of thesis_key -> section_name.
    e.g., {"abstract": "Preliminary Pages", "chapter1": "Chapter One", ...}
    """
    rubric = load_rubric(institution)
    mapping = {}
    for name, data in rubric["sections"].items():
        key = data.get("thesis_key")
        if key:
            mapping[key] = name
    return mapping
