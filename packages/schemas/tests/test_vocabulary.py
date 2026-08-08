"""match_to_vocabulary: strictest-first, deterministic, auditable. No fuzzy
matching anywhere — every case here either matches via an exact,
inspectable transformation or does not match at all."""

from schemas.vocabulary import find_whole_word_matches, match_to_vocabulary


def test_exact_match():
    term, method, confidence = match_to_vocabulary("PVC", ["Aluminum", "PVC", "Brass"])
    assert (term, method) == ("PVC", "exact")
    assert confidence == 1.0


def test_case_insensitive_match():
    term, method, _ = match_to_vocabulary("pvc", ["Aluminum", "PVC", "Brass"])
    assert (term, method) == ("PVC", "case_insensitive")


def test_normalized_match_punctuation_and_whitespace():
    term, method, _ = match_to_vocabulary(
        "  Stainless-Steel  ", ["Stainless Steel", "PVC"]
    )
    assert (term, method) == ("Stainless Steel", "normalized")


def test_normalized_match_aluminum_aluminium_spelling():
    term, method, _ = match_to_vocabulary("Aluminium", ["Aluminum", "PVC"])
    assert (term, method) == ("Aluminum", "normalized")


def test_normalized_match_colour_color_spelling():
    term, method, _ = match_to_vocabulary("Colour", ["Color", "Black"])
    assert (term, method) == ("Color", "normalized")


def test_normalized_match_grey_gray_spelling():
    term, method, _ = match_to_vocabulary("Gray", ["Grey", "Black"])
    assert (term, method) == ("Grey", "normalized")


def test_whole_word_containment_aluminum_alloy():
    term, method, _ = match_to_vocabulary(
        "Aluminum Alloy", ["Aluminium", "Stainless Steel", "PVC", "Brass", "Chrome"]
    )
    assert (term, method) == ("Aluminium", "whole_word_containment")


def test_whole_word_containment_multi_word_term():
    term, method, _ = match_to_vocabulary(
        "Brushed Steel Finish, matte", ["Brushed Steel", "Bright Chrome"]
    )
    assert (term, method) == ("Brushed Steel", "whole_word_containment")


def test_no_match_at_any_level_returns_none():
    term, method, confidence = match_to_vocabulary("Titanium", ["Aluminum", "PVC", "Brass"])
    assert term is None
    assert method == "no_match"
    assert confidence == 0.0


def test_near_miss_typo_is_not_fuzzy_matched():
    # "Alumnium" is one transposition away from "Aluminium" -- must NOT match;
    # this project never does edit-distance/fuzzy matching.
    term, method, _ = match_to_vocabulary("Alumnium", ["Aluminium", "PVC"])
    assert term is None
    assert method == "no_match"


def test_two_exact_duplicate_vocabulary_terms_is_ambiguous_not_forced():
    term, method, confidence = match_to_vocabulary("PVC", ["PVC", "PVC"])
    assert term is None
    assert method == "exact_ambiguous"
    assert confidence == 0.0


def test_multi_option_value_is_ambiguous_at_containment_level():
    term, method, confidence = match_to_vocabulary(
        "Silver/Golden/Bronze", ["Silver", "Gold", "Bronze", "Black"]
    )
    # "Silver" and "Bronze" are both present as whole words -- genuinely
    # ambiguous, never silently resolved to one.
    assert term is None
    assert method == "whole_word_containment_ambiguous"
    assert confidence == 0.0


def test_find_whole_word_matches_lists_every_candidate():
    matches = find_whole_word_matches("Silver/Golden/Bronze", ["Silver", "Gold", "Bronze", "Black"])
    assert matches == ["Silver", "Bronze"]


def test_find_whole_word_matches_empty_when_none_present():
    assert find_whole_word_matches("Titanium", ["Aluminum", "PVC"]) == []


def test_empty_raw_value_returns_no_match():
    term, method, confidence = match_to_vocabulary("", ["PVC", "Brass"])
    assert (term, method, confidence) == (None, "no_match", 0.0)


def test_empty_vocabulary_returns_no_match():
    term, method, confidence = match_to_vocabulary("PVC", [])
    assert (term, method, confidence) == (None, "no_match", 0.0)


def test_none_raw_value_returns_no_match_not_a_crash():
    term, method, confidence = match_to_vocabulary(None, ["PVC"])
    assert (term, method, confidence) == (None, "no_match", 0.0)
