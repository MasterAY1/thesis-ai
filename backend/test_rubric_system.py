"""Test rubric loader — Phase 1 verification."""
import sys; sys.path.insert(0, '.')
from services.rubric_loader import load_rubric, list_all_institutions, get_rubric_metadata
from services.rubric_validator import validate_rubric

print("=== NMCN ===")
r = load_rubric('nmcn')
print(f"  {r['institution_name']}: {r['total_marks']} marks, {len(r['sections'])} sections")
valid, errors = validate_rubric(r)
print(f"  Valid: {valid}, Errors: {len(errors)}")

print("\n=== NIGERIA GENERAL ===")
r = load_rubric('nigeria_general')
print(f"  {r['institution_name']}: {r['total_marks']} marks, {len(r['sections'])} sections")
valid, errors = validate_rubric(r)
print(f"  Valid: {valid}, Errors: {len(errors)}")
for e in errors:
    print(f"    {e}")

print("\n=== LASU (inherits from nigeria_general) ===")
r = load_rubric('lasu')
print(f"  {r['institution_name']}: {r['total_marks']} marks, {len(r['sections'])} sections")

print("\n=== UNILAG (inherits) ===")
r = load_rubric('unilag')
print(f"  {r['institution_name']}: {r['total_marks']} marks")

print("\n=== OAU (inherits) ===")
r = load_rubric('oau')
print(f"  {r['institution_name']}: {r['total_marks']} marks")

print("\n=== FUTA (inherits) ===")
r = load_rubric('futa')
print(f"  {r['institution_name']}: {r['total_marks']} marks")

print("\n=== UNKNOWN INSTITUTION (fallback) ===")
r = load_rubric('some_unknown_school')
print(f"  {r['institution_name']}: {r['total_marks']} marks (fallback)")

print("\n=== ALL INSTITUTIONS ===")
for i in list_all_institutions():
    print(f"  {i['code']:20s} {i['type']:15s} {i['name']}")

print("\n=== RUBRIC METADATA (nigeria_general) ===")
m = get_rubric_metadata('nigeria_general')
print(f"  {m['institution_name']}: {m['section_count']} sections, {m['total_marks']} marks")
for s in m['sections']:
    print(f"    {s['name']:30s} {s['total']:>5} marks  ({s['criteria_count']} criteria)")

print("\n=== BACKWARD COMPAT: NMCN unchanged ===")
r = load_rubric('nmcn')
assert r['total_marks'] == 100
assert r['institution_code'] == 'nmcn'
assert 'Preliminary Pages' in r['sections']
assert r['sections']['Preliminary Pages']['total'] == 8
print("  ALL ASSERTIONS PASSED OK")
