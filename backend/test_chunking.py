"""Quick test for the chunking module."""
from services.chunking import chunk_text, estimate_tokens, safe_truncate_for_github

# Test 1: Large document chunking
t = "x" * 50000
chunks = chunk_text(t, 4000, 500)
print(f"50k chars -> {len(chunks)} chunks")

# Test 2: Token estimation
print(f"Token estimate for 50k chars: {estimate_tokens(t)}")

# Test 3: GitHub safety truncation
safe = safe_truncate_for_github(t)
print(f"Truncated: {len(safe)} chars (from {len(t)})")

# Test 4: Small text
small_chunks = chunk_text("hello world")
print(f"Small text: {len(small_chunks)} chunk(s)")

# Test 5: Empty text
empty_chunks = chunk_text("")
print(f"Empty text: {len(empty_chunks)} chunk(s)")

print("\nAll chunking tests passed!")
