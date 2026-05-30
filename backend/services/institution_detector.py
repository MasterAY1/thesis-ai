"""
Multi-Dimensional Institution, Faculty, Department & Project Type Detector

Determines the university, department, school type, and project type from
the first page (first 3,000 characters) of the uploaded draft.
Ensures zero NMCN leakage for non-NMCN nursing departments.

Features:
  - Exact abbreviation and full name matching (12 institutions).
  - Fuzzy-matching fallbacks (Univ. of Lagos, Lagos State Univ., etc.).
  - Location context reinforcement (e.g. "Akoka" -> UNILAG, "Zaria" -> ABU).
  - School type categorization (professional / public / private).
  - Department and Faculty detection (Nursing, Computer Science, Mass Comm, etc.).
  - Professional vs academic Nursing exclusion logic.
  - Matched phrases extraction for evidence logging.
  - Project type classification (Proposal, Dissertation, IT Report, etc.).
"""
import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("thesis_ai.institution_detector")

# ── Institutions Data ─────────────────────────────────────────────────────────
INSTITUTIONS_DATA = {
    "nmcn": {
        "name": "Nursing and Midwifery Council of Nigeria",
        "type": "professional",
        "full_patterns": [
            re.compile(r"nursing\s+and\s+midwifery\s+council\s+of\s+nigeria", re.I),
            re.compile(r"nursing\s*(?:&|and)\s*midwifery\s+council", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bnmcn\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"school\s+of\s+nursing", re.I),
            re.compile(r"school\s+of\s+midwifery", re.I),
            re.compile(r"basic\s+nursing\s+(?:programme|program)", re.I),
        ],
        "locations": []
    },
    "unilag": {
        "name": "University of Lagos",
        "type": "public",
        "full_patterns": [
            re.compile(r"university\s+of\s+lagos", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bunilag\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"univ\.?\s+(of\s+)?lagos", re.I),
            re.compile(r"lagos\s+univ\.?", re.I),
            re.compile(r"unilag\s+akoka", re.I),
        ],
        "locations": ["akoka", "yaba"]
    },
    "lasu": {
        "name": "Lagos State University",
        "type": "public",
        "full_patterns": [
            re.compile(r"lagos\s+state\s+university", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\blasu\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"lagos\s+state\s+univ\.?", re.I),
            re.compile(r"lasu\s+ojo", re.I),
        ],
        "locations": ["ojo", "epe", "badagry"]
    },
    "ui": {
        "name": "University of Ibadan",
        "type": "public",
        "full_patterns": [
            re.compile(r"university\s+of\s+ibadan", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bui\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"univ\.?\s+(of\s+)?ibadan", re.I),
            re.compile(r"ibadan\s+univ\.?", re.I),
        ],
        "locations": ["ibadan"]
    },
    "unn": {
        "name": "University of Nigeria, Nsukka",
        "type": "public",
        "full_patterns": [
            re.compile(r"university\s+of\s+nigeria", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bunn\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"univ\.?\s+(of\s+)?nigeria", re.I),
            re.compile(r"nigeria\s+univ\.?", re.I),
            re.compile(r"unn\s+nsukka", re.I),
        ],
        "locations": ["nsukka", "enugu", "ituku-ozalla"]
    },
    "abu": {
        "name": "Ahmadu Bello University",
        "type": "public",
        "full_patterns": [
            re.compile(r"ahmadu\s+bello\s+university", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\babu\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"ahmadu\s+bello\s+univ\.?", re.I),
            re.compile(r"abu\s+zaria", re.I),
            re.compile(r"ahmadu\s+bello\b", re.I),
        ],
        "locations": ["zaria", "samaru"]
    },
    "oau": {
        "name": "Obafemi Awolowo University",
        "type": "public",
        "full_patterns": [
            re.compile(r"obafemi\s+awolowo\s+university", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\boau\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"obafemi\s+awolowo\s+univ\.?", re.I),
            re.compile(r"great\s+ife", re.I),
        ],
        "locations": ["ile-ife", "ife"]
    },
    "futa": {
        "name": "Federal University of Technology, Akure",
        "type": "public",
        "full_patterns": [
            re.compile(r"federal\s+university\s+of\s+technology\s+akure", re.I),
            re.compile(r"federal\s+university\s+of\s+technology,\s+akure", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bfuta\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"fed\.?\s+univ\.?\s+of\s+tech\.?\s+akure", re.I),
            re.compile(r"futa\s+akure", re.I),
        ],
        "locations": ["akure"]
    },
    "futo": {
        "name": "Federal University of Technology, Owerri",
        "type": "public",
        "full_patterns": [
            re.compile(r"federal\s+university\s+of\s+technology\s+owerri", re.I),
            re.compile(r"federal\s+university\s+of\s+technology,\s+owerri", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bfuto\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"fed\.?\s+univ\.?\s+of\s+tech\.?\s+owerri", re.I),
            re.compile(r"futo\s+owerri", re.I),
        ],
        "locations": ["owerri", "ihiagwa"]
    },
    "covenant": {
        "name": "Covenant University",
        "type": "private",
        "full_patterns": [
            re.compile(r"covenant\s+university", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bcovenant\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"covenant\s+univ\.?", re.I),
        ],
        "locations": ["ota", "canaanland"]
    },
    "babcock": {
        "name": "Babcock University",
        "type": "private",
        "full_patterns": [
            re.compile(r"babcock\s+university", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bbabcock\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"babcock\s+univ\.?", re.I),
        ],
        "locations": ["lishan", "lishon", "remo", "iko-remo"]
    },
    "uniben": {
        "name": "University of Benin",
        "type": "public",
        "full_patterns": [
            re.compile(r"university\s+of\s+benin", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\buniben\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"univ\.?\s+(of\s+)?benin", re.I),
            re.compile(r"benin\s+univ\.?", re.I),
        ],
        "locations": ["benin", "ubth", "uogbo"]
    },
    "unizik": {
        "name": "Nnamdi Azikiwe University",
        "type": "public",
        "full_patterns": [
            re.compile(r"nnamdi\s+azikiwe\s+university", re.I),
        ],
        "acronym_patterns": [
            re.compile(r"\bunizik\b", re.I),
        ],
        "fuzzy_patterns": [
            re.compile(r"nnamdi\s+azikiwe\s+univ\.?", re.I),
            re.compile(r"azikiwe\s+univ\.?", re.I),
        ],
        "locations": ["awka", "nnewi"]
    }
}

# ── Departments Data ──────────────────────────────────────────────────────────
DEPARTMENTS_DATA = {
    "department_of_nursing": {
        "name": "Department of Nursing",
        "faculty": "clinical_sciences",
        "patterns": [
            re.compile(r"department\s+of\s+nursing\s+science", re.I),
            re.compile(r"faculty\s+of\s+nursing", re.I),
            re.compile(r"dept\s+of\s+nursing", re.I),
            re.compile(r"\bnursing\s+science\b", re.I),
            re.compile(r"\bnursing\s+department\b", re.I),
        ]
    },
    "department_of_computer_science": {
        "name": "Department of Computer Science",
        "faculty": "science",
        "patterns": [
            re.compile(r"department\s+of\s+computer\s+science", re.I),
            re.compile(r"dept\s+of\s+computer\s+science", re.I),
            re.compile(r"\bcomputer\s+science\b", re.I),
        ]
    },
    "department_of_mass_communication": {
        "name": "Department of Mass Communication",
        "faculty": "social_sciences",
        "patterns": [
            re.compile(r"department\s+of\s+mass\s+communication", re.I),
            re.compile(r"dept\s+of\s+mass\s+communication", re.I),
            re.compile(r"\bmass\s+communication\b", re.I),
            re.compile(r"\bmass\s+comm\b", re.I),
        ]
    },
    "department_of_accounting": {
        "name": "Department of Accounting",
        "faculty": "management_sciences",
        "patterns": [
            re.compile(r"department\s+of\s+accounting", re.I),
            re.compile(r"dept\s+of\s+accounting", re.I),
            re.compile(r"\baccounting\b", re.I),
        ]
    },
    "department_of_biochemistry": {
        "name": "Department of Biochemistry",
        "faculty": "science",
        "patterns": [
            re.compile(r"department\s+of\s+biochemistry", re.I),
            re.compile(r"dept\s+of\s+biochemistry", re.I),
            re.compile(r"\bbiochemistry\b", re.I),
        ]
    },
    "department_of_microbiology": {
        "name": "Department of Microbiology",
        "faculty": "science",
        "patterns": [
            re.compile(r"department\s+of\s+microbiology", re.I),
            re.compile(r"dept\s+of\s+microbiology", re.I),
            re.compile(r"\bmicrobiology\b", re.I),
        ]
    }
}

# ── Project Types Data ────────────────────────────────────────────────────────
PROJECT_TYPES_DATA = {
    "undergraduate_project": [
        re.compile(r"undergraduate\s+project", re.I),
        re.compile(r"project\s+report", re.I),
        re.compile(r"b\.?sc\.?\s+project", re.I),
        re.compile(r"bsc\s+project", re.I),
        re.compile(r"submitted\s+in\s+partial\s+fulfillment\s+of\s+the\s+requirements", re.I),
    ],
    "proposal": [
        re.compile(r"research\s+proposal", re.I),
        re.compile(r"project\s+proposal", re.I),
        re.compile(r"thesis\s+proposal", re.I),
        re.compile(r"proposal\s+report", re.I),
    ],
    "siwes_report": [
        re.compile(r"siwes\s+report", re.I),
        re.compile(r"siwes\s+technical\s+report", re.I),
        re.compile(r"industrial\s+training\s+report", re.I),
        re.compile(r"\bit\s+report\b", re.I),
        re.compile(r"\bit\s+technical\s+report\b", re.I),
    ],
    "dissertation": [
        re.compile(r"dissertation", re.I),
        re.compile(r"doctor\s+of\s+philosophy", re.I),
        re.compile(r"ph\.?d\.?\s+dissertation", re.I),
    ],
    "thesis": [
        re.compile(r"m\.?sc\.?\s+thesis", re.I),
        re.compile(r"msc\s+thesis", re.I),
        re.compile(r"\bthesis\b", re.I),
        re.compile(r"master'?s\s+thesis", re.I),
        re.compile(r"master\s+of\s+science", re.I),
    ],
    "seminar": [
        re.compile(r"seminar\s+paper", re.I),
        re.compile(r"seminar\s+report", re.I),
        re.compile(r"academic\s+seminar", re.I),
    ]
}


# ── Core Detection API ────────────────────────────────────────────────────────

def detect_institution(text: str) -> Dict[str, Any]:
    """
    Scans the cover page text (first 3,000 chars) to detect:
      - Institution code & name
      - School type
      - Faculty
      - Department
      - Project type
      - Confidence score (0.0 to 1.0)
      - Evidence (matched phrases)
    """
    if not text:
        return {
            "institution": "nigeria_general",
            "faculty": "unknown",
            "department": "unknown",
            "school_type": "public",
            "project_type": "thesis",
            "confidence": 0.0,
            "method": "fallback",
            "matched_phrases": []
        }

    # Restrict scan to the cover page area (first 3,000 characters)
    scan_limit = min(3000, len(text))
    scan_text = text[:scan_limit].strip()
    scan_text_lower = scan_text.lower()

    # Track matched evidence phrases
    matched_evidence = []
    
    # ── 1. Detect Department and Faculty ──────────────────────────────────────
    detected_dept = "unknown"
    detected_faculty = "unknown"
    dept_score = 0.0

    for dept_code, dept_info in DEPARTMENTS_DATA.items():
        for pattern in dept_info["patterns"]:
            match = pattern.search(scan_text)
            if match:
                detected_dept = dept_code
                detected_faculty = dept_info["faculty"]
                matched_evidence.append(match.group().upper())
                break
        if detected_dept != "unknown":
            break

    # ── 2. Detect Project Type ────────────────────────────────────────────────
    detected_proj_type = "thesis"  # default safe fallback
    for proj_code, patterns in PROJECT_TYPES_DATA.items():
        for pattern in patterns:
            match = pattern.search(scan_text)
            if match:
                detected_proj_type = proj_code
                matched_evidence.append(match.group().upper())
                break
        if detected_proj_type != "thesis":
            break

    # ── 3. Detect Institution ─────────────────────────────────────────────────
    scores: Dict[str, float] = {}
    matched_methods: Dict[str, str] = {}
    
    for inst_code, data in INSTITUTIONS_DATA.items():
        score = 0.0
        method = "none"

        # ── EXACT matches (Full Names)
        for pattern in data["full_patterns"]:
            match = pattern.search(scan_text)
            if match:
                score = max(score, 1.0)
                method = "exact_match"
                matched_evidence.append(match.group().upper())

        # ── STANDALONE acronym matching
        for pattern in data["acronym_patterns"]:
            match = pattern.search(scan_text)
            if match:
                score = max(score, 0.95)
                method = "exact_match"
                matched_evidence.append(match.group().upper())

        # ── FUZZY matches (Regex aliases)
        for pattern in data["fuzzy_patterns"]:
            match = pattern.search(scan_text)
            if match:
                score = max(score, 0.85)
                if method == "none":
                    method = "fuzzy_match"
                matched_evidence.append(match.group().upper())

        # ── Location context reinforcement
        if score > 0.0 and score < 1.0:
            for loc in data["locations"]:
                if re.search(rf"\b{loc}\b", scan_text_lower):
                    score = min(1.0, score + 0.05)
                    matched_evidence.append(loc.upper())

        if score > 0.0:
            scores[inst_code] = score
            matched_methods[inst_code] = method

    # ── 4. Apply HOD/Faculty Nursing Science Exclusions ────────────────────────
    # NMCN is a professional council rubric, not a university nursing degree rubric.
    # Academic nursing projects should NOT grade against NMCN unless they are from a 
    # specific School of Nursing/Midwifery or specify basic programme.
    if "nmcn" in scores:
        # Check if School of Nursing / Midwifery / Basic Nursing appears
        has_strict_professional = any(
            p.search(scan_text) for p in INSTITUTIONS_DATA["nmcn"]["fuzzy_patterns"]
        ) or any(
            p.search(scan_text) for p in INSTITUTIONS_DATA["nmcn"]["full_patterns"]
        )

        # If it doesn't contain strict school of nursing phrases, it is academic nursing!
        if not has_strict_professional:
            logger.info("Department Science nursing exclusion triggered: removing NMCN from candidates")
            scores.pop("nmcn", None)

    # ── 5. Select Winner ──────────────────────────────────────────────────────
    if not scores:
        return {
            "institution": "nigeria_general",
            "faculty": detected_faculty,
            "department": detected_dept,
            "school_type": "public",
            "project_type": detected_proj_type,
            "confidence": 0.0,
            "method": "fallback",
            "matched_phrases": list(set(matched_evidence))
        }

    winner = max(scores, key=scores.get)
    confidence = scores[winner]
    method = matched_methods[winner]

    # Post-reinforce confidence if department matches the institution
    # E.g. matching "University of Lagos" AND "Department of Computer Science" strengthens UNILAG match
    if detected_dept != "unknown" and winner != "nmcn":
        confidence = min(1.0, confidence + 0.02)

    return {
        "institution": winner,
        "faculty": detected_faculty,
        "department": detected_dept,
        "school_type": INSTITUTIONS_DATA[winner]["type"],
        "project_type": detected_proj_type,
        "confidence": round(confidence, 2),
        "method": method,
        "matched_phrases": list(set(matched_evidence))
    }
