"""
api_client.py - Client API
"""

import requests

class APIClient:
    """Client pour une API REST"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.history = []
    
    def get(self, endpoint: str) -> dict:
        """Requête GET"""
        response = self.session.get(f"{self.base_url}/{endpoint}")
        self.history.append(f"GET {endpoint}: {response.status_code}")
        return response.json()
    
    def post(self, endpoint: str, data: dict) -> dict:
        """Requête POST"""
        response = self.session.post(f"{self.base_url}/{endpoint}", json=data)
        self.history.append(f"POST {endpoint}: {response.status_code}")
        return response.json()
    
    
    
    def get_history(self) -> list:
        """Retourne l'historique des requêtes"""
        return self.history
    