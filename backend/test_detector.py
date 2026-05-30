"""Unit tests for multi-dimensional institution, department, and project type detector."""
import sys; sys.path.insert(0, '.')
from services.institution_detector import detect_institution

def run_tests():
    print("=== START DETECTOR TESTS ===")

    # Test 1: Exact Match UNILAG
    text_unilag = (
        "A Research Project Report on Burnout Syndrome\n"
        "Presented to the DEPARTMENT OF COMPUTER SCIENCE\n"
        "FACULTY OF SCIENCE, UNIVERSITY OF LAGOS, AKOKA\n"
        "By John Doe, Matric: 180302022\n"
        "Submitted in partial fulfillment of the requirements..."
    )
    r1 = detect_institution(text_unilag)
    print("Test 1: UNILAG")
    print(f"  Institution: {r1['institution']} (expected 'unilag')")
    print(f"  Confidence:  {r1['confidence']:.2f}")
    print(f"  Dept/Faculty: {r1['department']} / {r1['faculty']}")
    print(f"  Project type: {r1['project_type']} (expected 'undergraduate_project')")
    print(f"  Matches:     {r1['matched_phrases']}")
    assert r1['institution'] == 'unilag'
    assert r1['department'] == 'department_of_computer_science'
    assert r1['project_type'] == 'undergraduate_project'

    # Test 2: Babcock University Private
    text_babcock = (
        "AN EMPIRICAL STUDY ON MICROBIOLOGY PHASES\n"
        "By Babcock Student, Department of Microbiology\n"
        "BABCOCK UNIVERSITY, Ilishon-Remo, Ogun State\n"
        "Dissertation submitted to the post-graduate school..."
    )
    r2 = detect_institution(text_babcock)
    print("\nTest 2: Babcock")
    print(f"  Institution: {r2['institution']} (expected 'babcock')")
    print(f"  School Type: {r2['school_type']} (expected 'private')")
    print(f"  Dept:        {r2['department']} (expected 'department_of_microbiology')")
    print(f"  Project:     {r2['project_type']} (expected 'dissertation')")
    assert r2['institution'] == 'babcock'
    assert r2['school_type'] == 'private'
    assert r2['department'] == 'department_of_microbiology'
    assert r2['project_type'] == 'dissertation'

    # Test 3: Department Nursing science (LASU) -> Nursing Exclusion trigger!
    text_lasu_nursing = (
        "An investigation into clinical handwashing practices\n"
        "Submitted by LASU Nursing Student\n"
        "Department of Nursing Science, Faculty of Clinical Sciences\n"
        "LAGOS STATE UNIVERSITY, OJO\n"
        "June 2026."
    )
    r3 = detect_institution(text_lasu_nursing)
    print("\nTest 3: LASU Nursing (Exclusion Test)")
    print(f"  Institution: {r3['institution']} (expected 'lasu' - NOT 'nmcn')")
    print(f"  Dept:        {r3['department']} (expected 'department_of_nursing')")
    print(f"  Confidence:  {r3['confidence']}")
    assert r3['institution'] == 'lasu'
    assert r3['department'] == 'department_of_nursing'

    # Test 4: Strict Professional NMCN matches
    text_nmcn = (
        "Case Study on Maternal Health Care delivery\n"
        "Presented to the SCHOOL OF NURSING, UBTH, BENIN CITY\n"
        "In partial fulfillment for the award of basic nursing programme\n"
        "Nursing and Midwifery Council of Nigeria exam revision"
    )
    r4 = detect_institution(text_nmcn)
    print("\nTest 4: Strict NMCN Professional")
    print(f"  Institution: {r4['institution']} (expected 'nmcn')")
    print(f"  School Type: {r4['school_type']} (expected 'professional')")
    assert r4['institution'] == 'nmcn'
    assert r4['school_type'] == 'professional'

    # Test 5: Low confidence fallback to general
    text_unknown = (
        "Some random document title\n"
        "This doesn't mention any school or department.\n"
        "Just has some general guidelines and lists..."
    )
    r5 = detect_institution(text_unknown)
    print("\nTest 5: Fallback general")
    print(f"  Institution: {r5['institution']} (expected 'nigeria_general')")
    print(f"  Confidence:  {r5['confidence']:.2f}")
    assert r5['institution'] == 'nigeria_general'
    assert r5['confidence'] == 0.0

    print("\n=== ALL DETECTOR TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_tests()
