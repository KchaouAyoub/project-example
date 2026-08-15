"""
tests/test_api_client.py - Tests pour api_client
"""

from api_client import APIClient

def test_api_client_init():
    client = APIClient("https://api.example.com")
    assert client.base_url == "https://api.example.com"
    assert client.history == []

def test_api_client_get_history():
    client = APIClient("https://api.example.com")
    assert client.get_history() == []