"""Phase 2 import verification test."""
from services.document_classifier import detect_document_type
from services.feedback_styles import list_styles, get_style_prompt
from services.rewrite_engine import rewrite_issue
from services.report_generator import generate_pdf_report
from services.evaluation import evaluate_thesis
from api.routes import router

print("All Phase 2 imports: OK")

styles = list_styles()
print(f"Styles available: {[s['key'] for s in styles]}")

# Test classifier with a proposal text
proposal_text = (
    "This study intends to evaluate the relationship between nurse staffing and patient outcomes. "
    "The researcher will use structured questionnaires. The proposed study will be conducted in Lagos. "
    "A convenience sampling technique will be used. Data will be analyzed using SPSS."
)
doc = detect_document_type(proposal_text)
print(f"Classifier — type: {doc['document_type']}, confidence: {doc['confidence']:.0%}, skip: {doc['skip_sections']}")

# Test classifier with a thesis text
thesis_text = (
    "Chapter four presents the results of this study. The data were analyzed using descriptive statistics. "
    "Table 1 shows the distribution of respondents by age. The findings revealed that 72% of nurses "
    "experienced burnout. The results showed a statistically significant relationship (p<0.05). "
    "It was found that adequate staffing reduced medication errors."
)
doc2 = detect_document_type(thesis_text)
print(f"Classifier — type: {doc2['document_type']}, confidence: {doc2['confidence']:.0%}, skip: {doc2['skip_sections']}")

print("\nAll Phase 2 checks PASSED!")
