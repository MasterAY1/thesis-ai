import traceback
from services import evaluation, validation_engine

def mock_split(*args, **kwargs):
    return {"abstract": None, "chapter1": "Some text", "chapter3": "Some text", "chapter4": "Some text", "chapter5": "Some text"}

def mock_generate(*args, **kwargs):
    return {"issues": [{"issue_title": "Test", "severity": "low", "recoverable_marks": 1, "rubric": {"section": "Chapter One"}}], "status": "pass"}

evaluation.generate_json_response = mock_generate
validation_engine.generate_json_response = mock_generate
evaluation.split_thesis_sections = mock_split

try:
    res = evaluation.evaluate_thesis("dummy")
    print("SUCCESS")
except Exception as e:
    traceback.print_exc()
