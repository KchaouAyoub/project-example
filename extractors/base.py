"""
extractors/base.py - Classe de base pour tous les extracteurs
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseExtractor(ABC):
    """Classe de base pour l'extraction de fonctions."""
    
    @abstractmethod
    def extract(self, code: str, filename: str = "<memory>") -> List[Dict[str, Any]]:
        """
        Extrait les fonctions d'un code source.
        """
        pass
    
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Retourne les extensions de fichiers supportées."""
        pass
    
    @abstractmethod
    def language_name(self) -> str:
        """Retourne le nom du langage."""
        pass