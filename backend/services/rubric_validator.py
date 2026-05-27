"""
Rubric Validator

Validates rubric structures before evaluation to prevent grading errors.
Checks:
  - Total marks sum to expected total (default 100)
  - No negative marks
  - All required sections exist
  - No duplicate sections
  - Criteria marks sum to section total
  - Valid thesis_key mappings
  - Proper JSON structure

If invalid: caller should fallback to nigeria_general.
"""
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("thesis_ai.rubric_validator")

# Required thesis_key mappings for Nigerian thesis projects
REQUIRED_THESIS_KEYS = {
    "abstract", "chapter1", "chapter2", "chapter3",
    "chapter4", "chapter5", "references",
}

# Tolerance for floating point mark sums
MARK_SUM_TOLERANCE = 0.5


class RubricValidationError:
    """A single validation issue."""
    def __init__(self, level: str, message: str, field: str = ""):
        self.level = level  # "error" | "warning"
        self.message = message
        self.field = field

    def to_dict(self) -> dict:
        return {"level": self.level, "message": self.message, "field": self.field}

    def __repr__(self):
        return f"{self.level.upper()}: {self.message}"


def validate_rubric(
    rubric: Dict[str, Any],
    expected_total: int = 100,
) -> Tuple[bool, List[RubricValidationError]]:
    """
    Validate a rubric structure.

    Returns:
        (is_valid, errors)
        is_valid: True if no critical errors (warnings are OK)
        errors: list of RubricValidationError
    """
    errors: List[RubricValidationError] = []

    # ── 1. Basic structure checks ─────────────────────────────────────────────
    if not isinstance(rubric, dict):
        errors.append(RubricValidationError("error", "Rubric must be a JSON object"))
        return False, errors

    if "sections" not in rubric:
        errors.append(RubricValidationError("error", "Rubric missing 'sections' field"))
        return False, errors

    sections = rubric.get("sections", {})
    if not isinstance(sections, dict) or len(sections) == 0:
        errors.append(RubricValidationError("error", "Rubric 'sections' must be a non-empty object"))
        return False, errors

    # ── 2. Check total marks ──────────────────────────────────────────────────
    declared_total = rubric.get("total_marks", expected_total)
    actual_total = sum(s.get("total", 0) for s in sections.values() if isinstance(s, dict))

    if abs(actual_total - declared_total) > MARK_SUM_TOLERANCE:
        errors.append(RubricValidationError(
            "error",
            f"Section totals ({actual_total}) don't sum to declared total ({declared_total})",
            "total_marks"
        ))

    if abs(actual_total - expected_total) > MARK_SUM_TOLERANCE:
        errors.append(RubricValidationError(
            "warning",
            f"Total marks ({actual_total}) differ from expected {expected_total}",
            "total_marks"
        ))

    # ── 3. Check each section ─────────────────────────────────────────────────
    seen_thesis_keys = set()

    for section_name, section_data in sections.items():
        if not isinstance(section_data, dict):
            errors.append(RubricValidationError(
                "error", f"Section '{section_name}' must be an object", section_name
            ))
            continue

        # Check total marks
        section_total = section_data.get("total", 0)
        if section_total < 0:
            errors.append(RubricValidationError(
                "error", f"Section '{section_name}' has negative marks ({section_total})", section_name
            ))

        if section_total == 0:
            errors.append(RubricValidationError(
                "warning", f"Section '{section_name}' has 0 marks", section_name
            ))

        # Check criteria
        criteria = section_data.get("criteria", {})
        if not isinstance(criteria, dict):
            errors.append(RubricValidationError(
                "error", f"Section '{section_name}' criteria must be an object", section_name
            ))
            continue

        if len(criteria) == 0:
            errors.append(RubricValidationError(
                "warning", f"Section '{section_name}' has no criteria", section_name
            ))

        # Check for negative criterion marks
        for criterion_name, marks in criteria.items():
            if not isinstance(marks, (int, float)):
                errors.append(RubricValidationError(
                    "error",
                    f"Section '{section_name}', criterion '{criterion_name}': marks must be a number, got {type(marks).__name__}",
                    section_name
                ))
            elif marks < 0:
                errors.append(RubricValidationError(
                    "error",
                    f"Section '{section_name}', criterion '{criterion_name}': negative marks ({marks})",
                    section_name
                ))

        # Check criteria sum vs section total
        criteria_sum = sum(v for v in criteria.values() if isinstance(v, (int, float)))
        if abs(criteria_sum - section_total) > MARK_SUM_TOLERANCE:
            errors.append(RubricValidationError(
                "warning",
                f"Section '{section_name}': criteria sum ({criteria_sum}) differs from section total ({section_total})",
                section_name
            ))

        # Check thesis_key
        thesis_key = section_data.get("thesis_key")
        if thesis_key is not None:
            if thesis_key in seen_thesis_keys:
                errors.append(RubricValidationError(
                    "error",
                    f"Duplicate thesis_key '{thesis_key}' in section '{section_name}'",
                    section_name
                ))
            seen_thesis_keys.add(thesis_key)

    # ── 4. Check required thesis keys ─────────────────────────────────────────
    missing_keys = REQUIRED_THESIS_KEYS - seen_thesis_keys
    if missing_keys:
        errors.append(RubricValidationError(
            "warning",
            f"Missing thesis_key mappings: {', '.join(sorted(missing_keys))}. These sections won't be evaluated.",
            "thesis_keys"
        ))

    # ── 5. Determine validity ─────────────────────────────────────────────────
    has_errors = any(e.level == "error" for e in errors)
    is_valid = not has_errors

    if errors:
        for e in errors:
            if e.level == "error":
                logger.error(f"Rubric validation: {e}")
            else:
                logger.warning(f"Rubric validation: {e}")
    else:
        logger.info("Rubric validation: PASSED (no issues)")

    return is_valid, errors


def validate_and_fix(
    rubric: Dict[str, Any],
    expected_total: int = 100,
) -> Tuple[Dict[str, Any], List[RubricValidationError]]:
    """
    Validate a rubric and attempt to fix recoverable issues.

    Fixes applied:
      - Remove sections with negative marks (set to 0)
      - Remove criteria with non-numeric marks
      - Normalize total_marks if sections don't sum correctly

    Returns: (fixed_rubric, errors_after_fix)
    """
    is_valid, errors = validate_rubric(rubric, expected_total)

    if is_valid:
        return rubric, errors

    # Attempt fixes
    fixed = dict(rubric)
    fixed_sections = dict(rubric.get("sections", {}))

    for section_name, section_data in list(fixed_sections.items()):
        if not isinstance(section_data, dict):
            del fixed_sections[section_name]
            continue

        # Fix negative marks
        if section_data.get("total", 0) < 0:
            section_data["total"] = 0

        # Fix criteria
        criteria = section_data.get("criteria", {})
        if isinstance(criteria, dict):
            cleaned = {}
            for k, v in criteria.items():
                if isinstance(v, (int, float)) and v >= 0:
                    cleaned[k] = v
            section_data["criteria"] = cleaned

    fixed["sections"] = fixed_sections

    # Recalculate total
    actual_total = sum(
        s.get("total", 0) for s in fixed_sections.values()
        if isinstance(s, dict)
    )
    fixed["total_marks"] = actual_total

    # Re-validate
    is_valid_now, new_errors = validate_rubric(fixed, expected_total)

    return fixed, new_errors
