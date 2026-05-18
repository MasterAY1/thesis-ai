"""
Quick smoke test — mocks the AI router to test the evaluation pipeline
without making real API calls.
"""
import traceback
from unittest.mock import patch, MagicMock

# Mock router that returns valid section/evaluation data
def mock_generate(system_prompt, user_prompt, task="general", model_override=None):
    if task == "extract_sections":
        return {
            "abstract": "This is the abstract text.",
            "chapter1": "Chapter one introduction text with objectives.",
            "chapter2": "Chapter two literature review text.",
            "chapter3": "Chapter three methodology text with research design.",
            "chapter4": "Chapter four results text with findings.",
            "chapter5": "Chapter five discussion and conclusion.",
            "references": "List of references.",
            "_meta": {"provider": "mock", "task": task, "latency_s": 0.01, "fallback_used": False},
        }
    elif task == "cross_section_consistency":
        return {
            "status": "pass",
            "explanation": "Sections are consistent.",
            "evidence": [],
            "suggested_fix": None,
            "_meta": {"provider": "mock", "task": task, "latency_s": 0.01, "fallback_used": False},
        }
    else:
        return {
            "issues": [
                {
                    "issue_title": "Test Issue",
                    "severity": "low",
                    "recoverable_marks": 1,
                    "rubric": {"section": "Chapter One", "max_marks": 10, "expected_requirement": "Test"},
                }
            ],
            "_meta": {"provider": "mock", "task": task, "latency_s": 0.01, "fallback_used": False},
        }


# Patch the router singleton
mock_router = MagicMock()
mock_router.generate = mock_generate

try:
    with patch("services.ai.router.get_router", return_value=mock_router):
        from services.evaluation import evaluate_thesis
        res = evaluate_thesis("dummy thesis text")
        print("SUCCESS")
        print(f"  Overall score: {res.get('overall_score', 'N/A')}")
        print(f"  Deductions: {len(res.get('deductions', []))}")
        print(f"  Cross-validation: {res.get('cross_validation', {}).get('summary', 'N/A')}")
except Exception as e:
    traceback.print_exc()
