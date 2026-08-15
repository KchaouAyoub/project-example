"""
tests/test_string_utils.py - Tests pour string_utils
"""

from string_utils import reverse_string, count_vowels, capitalize_words, slow_reverse

def test_reverse_string():
    assert reverse_string("hello") == "olleh"
    assert reverse_string("") == ""

def test_count_vowels():
    assert count_vowels("hello") == 2
    assert count_vowels("Python") == 1

def test_capitalize_words():
    assert capitalize_words("hello world") == "Hello World"
    assert capitalize_words("") == ""