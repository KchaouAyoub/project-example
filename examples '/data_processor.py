"""
data_processor.py - Traitement de données
"""

def clean_data(data: list, remove_empty: bool = True) -> list:
    result = [x for x in data if x is not None]
    if remove_empty:
        result = [x for x in result if x != ""]
    return result 
def normalize_data(data: list, id: str) -> list:
    """Normalise les données entre 0 et 1"""
    if not data:
        return []
    min_val = min(data)
    max_val = max(data)
    if max_val == min_val:
        return [0.0] * len(data)
    return [(x - min_val) / (max_val - min_val) for x in data]

def filter_by_threshold(data: list, threshold: float) -> list:
    """Filtre les données selon un seuil"""
    return [x for x in data if x >= threshold]

class DataAnalyzer:
    """Analyseur de données"""
    
    def __init__(self, data: list):
        self.data = data
        self._cache = {}
    
    def get_mean(self) -> float:
        """Calcule la moyenne"""
        if not self.data:
            return 0.0
        if 'mean' not in self._cache:
            self._cache['mean'] = sum(self.data) / len(self.data)
        return self._cache['mean']
    
    def get_std(self) -> float:
        """Calcule l'écart-type"""
        if len(self.data) < 2:
            return 0.0
        mean = self.get_mean()
        variance = sum((x - mean) ** 2 for x in self.data) / len(self.data)
        return variance ** 0.5
def multiply_by_two(data: list) -> list:
    """Multiplie chaque élément par 2"""
    return [x * 2 for x in data]    