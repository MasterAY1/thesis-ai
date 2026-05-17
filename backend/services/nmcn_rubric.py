# NMCN Official Rubric Configuration
# Source: Nursing and Midwifery Council of Nigeria
# "Format for Writing and Scoring Research Projects"

NMCN_RUBRIC = {
    "Preliminary Pages": {
        "total": 8,
        "criteria": {
            "Cover Page": 0.25,
            "Title Page": 0.25,
            "Declaration Page": 0.25,
            "Certification/Approval Page": 0.25,
            "Abstract - Introduction": 1,
            "Abstract - Aim/Purpose of Study": 0.5,
            "Abstract - Methodology": 1,
            "Abstract - Results": 1,
            "Abstract - Conclusion/Recommendation": 1,
            "Abstract - Keywords (4-6)": 0.5,
            "Acknowledgment (max 1 page)": 0.5,
            "Table of Contents": 0.5,
            "List of Tables": 0.5,
            "List of Figures": 0.5,
        }
    },
    "Chapter One": {
        "total": 15,
        "criteria": {
            "Background to the Study": 3,
            "Statement of Problem": 2,
            "Objectives of the Study": 2,
            "Research Questions/Hypothesis": 2,
            "Significance of the Study": 2,
            "Scope of Study": 2,
            "Operational Definition of Terms": 2,
        }
    },
    "Chapter Two": {
        "total": 12,
        "criteria": {
            "Conceptual Review": 3,
            "Theoretical Review/Framework": 1,
            "Empirical Review": 5,
            "Proper Referencing within text (APA)": 1,
            "Currency of references (Books 10yrs, Journals 5yrs)": 2,
        }
    },
    "Chapter Three": {
        "total": 20,
        "criteria": {
            "Research Design": 1,
            "Setting (geographical location and characteristics)": 2,
            "Target Population": 1,
            "Sampling (size and formula)": 1,
            "Sampling Technique (method, description, inclusion criteria)": 3,
            "Instruments for Data Collection (types, nature, item number)": 1,
            "Validity of Instrument (face and content)": 1,
            "Reliability of Instrument (test and reliability index)": 3,
            "Method of Data Collection (administration, duration, sample)": 3,
            "Method of Data Analysis (technique and explanation)": 2,
            "Ethical Consideration (approval, consent)": 2,
        }
    },
    "Chapter Four": {
        "total": 15,
        "criteria": {
            "Presentation of Results using tables and figures": 4,
            "Proper labelling of tables and figures": 3,
            "Proper description of content of tables and figures": 4,
            "Answering research questions/hypothesis": 4,
        }
    },
    "Chapter Five": {
        "total": 20,
        "criteria": {
            "Identify key findings": 2,
            "State implications of findings with literature support": 5,
            "Align findings with previous studies cited": 2,
            "Implications of findings to Nursing": 2,
            "Limitations of the study": 1,
            "Summary of the study": 2,
            "Conclusion": 2,
            "Recommendations": 3,
            "Suggestions for further studies": 1,
        }
    },
    "References and Appendix": {
        "total": 7,
        "criteria": {
            "Proper use of APA format (7th Edition)": 3,
            "Alphabetical arrangement": 1,
            "Proper punctuation": 1,
            "Appendices (content)": 2,
        }
    },
    "Typing Instructions": {
        "total": 3,
        "criteria": {
            "Formatting (Times New Roman, Font 12)": 0.5,
            "Double line spacing": 0.5,
            "Paragraphing (block style)": 0.5,
            "Pagination": 0.5,
            "Quotations (proper format)": 0.5,
            "Quality of Illustration": 0.5,
        }
    },
}

# Flat section map for the scoring engine (section name -> max marks)
RUBRIC = {section: data["total"] for section, data in NMCN_RUBRIC.items()}
# Add "General" for cross-cutting issues
RUBRIC["General"] = 0
