"""
extractors/__init__.py - Détecteur de langage
"""

from typing import List, Dict, Any
from .base import BaseExtractor
from .python_extractor import PythonExtractor
from .java_extractor import JavaExtractor
from .cpp_extractor import CppExtractor

# Tous les extracteurs disponibles
EXTRACTORS = [
    PythonExtractor(),
    JavaExtractor(),
    CppExtractor(),
]

SUPPORTED_EXTENSIONS = {
    extension
    for extractor in EXTRACTORS
    for extension in extractor.supported_extensions()
}

def get_extractor(filename: str) -> BaseExtractor | None:
    """
    Retourne l'extracteur correspondant à l'extension du fichier.
    """
    import os
    ext = os.path.splitext(filename)[1].lower()
    for extractor in EXTRACTORS:
        if ext in extractor.supported_extensions():
            return extractor
    return None

def extract_functions(code: str, filename: str = "<memory>") -> List[Dict[str, Any]]:
    """
    Extrait les fonctions d'un fichier en fonction de son extension.
    """
    extractor = get_extractor(filename)
    if extractor:
        return extractor.extract(code, filename)
    return []