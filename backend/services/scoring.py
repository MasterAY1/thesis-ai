from typing import Dict, Any, List
from .rubric_loader import get_flat_rubric

def calculate_score(issues: List[Dict[str, Any]], institution: str = "nmcn") -> Dict[str, Any]:
    """
    Takes rubric-aware issues identified by the AI and mathematically calculates
    the final scores, deductions, and projected improvements.
    Dynamically loads the rubric for the specified institution.
    """
    RUBRIC = get_flat_rubric(institution)
    
    # Initialize breakdown with perfect scores
    breakdown = {}
    for section, max_score in RUBRIC.items():
        if section != "General":
            breakdown[section] = {"score": max_score, "max": max_score}
        
    total_max = sum(v for k, v in RUBRIC.items() if k != "General")
    total_deductions = 0
    
    formatted_deductions = []
    improvements = []
    
    for issue in issues:
        rubric_obj = issue.get("rubric", {})
        section = rubric_obj.get("section", issue.get("rubric_section", "General"))
        
        # Normalize section names
        if section not in RUBRIC:
            for rub_sec in RUBRIC:
                if rub_sec.lower() in section.lower() or section.lower() in rub_sec.lower():
                    section = rub_sec
                    break
        
        deduction = issue.get("recoverable_marks", 0)
        
        if section in breakdown:
            actual_deduction = min(deduction, breakdown[section]["score"])
            if actual_deduction > 0:
                breakdown[section]["score"] -= actual_deduction
        else:
            actual_deduction = deduction

        if actual_deduction > 0:
            total_deductions += actual_deduction
            section_max = RUBRIC.get(section, 0)
            
            formatted_deductions.append({
                "section": section,
                "issue_title": issue.get("issue_title", "Unknown issue"),
                "severity": issue.get("severity", "medium"),
                "rubric": {
                    "section": section,
                    "max_marks": rubric_obj.get("max_marks", section_max),
                    "expected_requirement": rubric_obj.get("expected_requirement", ""),
                },
                "evidence": issue.get("evidence", {}),
                "deduction_reasoning": issue.get("deduction_reasoning", ""),
                "supervisor_note": issue.get("supervisor_note", ""),
                "suggested_fix": issue.get("suggested_fix", ""),
                "deduction": actual_deduction
            })
            
            if issue.get("suggested_fix"):
                improvements.append({
                    "text": issue.get("suggested_fix"),
                    "issue_title": issue.get("issue_title", "Issue"),
                    "marks_recovered": actual_deduction
                })

    overall_score = round(total_max - total_deductions, 1)
    projected_score = round(overall_score + sum(imp["marks_recovered"] for imp in improvements), 1)
    
    # Round section scores to eliminate floating point artifacts
    for section_key in breakdown:
        breakdown[section_key]["score"] = round(breakdown[section_key]["score"], 1)
    
    feedback = [f"{d['section']}: {d['issue_title']} (-{d['deduction']} marks)" for d in formatted_deductions]
    if not feedback:
        feedback = ["Excellent work! No major deductions found."]
        
    return {
        "overall_score": overall_score,
        "total_marks": total_max,
        "projected_score": projected_score,
        "breakdown": breakdown,
        "deductions": formatted_deductions,
        "feedback": feedback,
        "improvements": improvements
    }
