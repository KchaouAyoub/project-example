"""
tests/test_data_processor.py - Tests pour data_processor
"""

from data_processor import clean_data, normalize_data, filter_by_threshold, DataAnalyzer

def test_clean_data():
    assert clean_data([1, None, 2, None, 3]) == [1, 2, 3]
    assert clean_data([]) == []

def test_normalize_data():
    assert normalize_data([1, 2, 3, 4, 5]) == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert normalize_data([]) == []

def test_filter_by_threshold():
    assert filter_by_threshold([1, 2, 3, 4, 5], 3) == [3, 4, 5]
    assert filter_by_threshold([], 0) == []

def test_data_analyzer_mean():
    analyzer = DataAnalyzer([1, 2, 3, 4, 5])
    assert analyzer.get_mean() == 3.0

def test_data_analyzer_std():
    analyzer = DataAnalyzer([1, 2, 3, 4, 5])
    assert round(analyzer.get_std(), 2) == 1.41