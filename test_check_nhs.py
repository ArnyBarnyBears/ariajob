import pytest
from check_nhs import is_match

# Helper to build a minimal job dict
def job(title, employer):
    return {"title": title, "employer": employer, "date_posted": "", "closing": "", "salary": "", "link": ""}


# --- Should MATCH ---

def test_exact_title_match():
    assert is_match(job("Assistant Psychologist", "Some NHS Trust London SW1"))

def test_title_match_lowercase():
    assert is_match(job("assistant psychologist", "Some NHS Trust London SW1"))

def test_title_match_mixed_case():
    assert is_match(job("ASSISTANT PSYCHOLOGIST", "Some NHS Trust London SW1"))

def test_title_match_with_extra_words():
    assert is_match(job("Band 5 Assistant Psychologist - CAMHS", "Some NHS Trust"))

def test_employer_match_by_trust_name():
    assert is_match(job("Unrelated Job Title", "South West London and St Georges Mental Health NHS Trust SW17 0YF"))

def test_employer_match_by_postcode():
    assert is_match(job("Unrelated Job Title", "Some Trust London SW17 0YF"))

def test_employer_match_trust_name_lowercase():
    assert is_match(job("Unrelated Job Title", "south west london and st georges mental health nhs trust"))

def test_both_title_and_employer_match():
    assert is_match(job("Assistant Psychologist", "South West London and St Georges Mental Health NHS Trust SW17 0YF"))


# --- Should NOT MATCH ---

def test_no_match_unrelated_title_and_employer():
    assert not is_match(job("Staff Nurse", "Royal London Hospital E1 1BB"))

def test_no_match_partial_title_word():
    # "psychologist" alone without "assistant" should not match
    assert not is_match(job("Clinical Psychologist", "Some Trust London"))

def test_no_match_similar_postcode():
    # SW17 1AA is not SW17 0YF
    assert not is_match(job("Admin Role", "Some Trust London SW17 1AA"))

def test_no_match_assistant_in_different_context():
    # "assistant" alone shouldn't match
    assert not is_match(job("Admin Assistant Band 2", "Some Trust London"))