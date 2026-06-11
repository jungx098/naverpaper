"""Tests for username masking in npaper.py."""

from npaper import mask_username


def test_empty_returns_empty():
    assert mask_username("") == ""


def test_single_char_reveals_nothing():
    masked = mask_username("a")
    assert masked == "******"
    assert "a" not in masked


def test_two_chars_reveal_nothing():
    masked = mask_username("ab")
    assert masked == "******"
    assert "a" not in masked
    assert "b" not in masked


def test_three_or_four_chars_reveal_only_first():
    assert mask_username("abc") == "a******"
    assert mask_username("abcd") == "a******"
    # The last character must not leak for short usernames.
    assert "c" not in mask_username("abc")
    assert "d" not in mask_username("abcd")


def test_long_reveals_first_and_last():
    assert mask_username("johndoe") == "j******e"


def test_fixed_width_hides_true_length():
    # Different-length usernames produce the same number of mask characters,
    # so the mask does not leak the username length.
    assert mask_username("abcde").count("*") == mask_username("abcdefghij").count("*")
