import traceback
from services.evaluation import evaluate_thesis

try:
    print("Testing evaluate_thesis...")
    res = evaluate_thesis("test content")
    print(res)
except Exception as e:
    traceback.print_exc()
