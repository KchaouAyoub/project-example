"""
string_utils.py - Utilitaires pour les chaînes de caractères
"""

import asyncio
import time

def reverse_string(text: str) -> str:
    """Inverse une chaîne"""
    return text[::-1]

def count_vowels(text: str) -> int:
    """Compte les voyelles"""
    vowels = 'aeiouyAEIOUY'
    return sum(1 for c in text if c in vowels)

def capitalize_words(text: str) -> str:
    """Met en majuscule chaque mot"""
    return ' '.join(word.capitalize() for word in text.split())

def timer(func):
    """Décorateur pour mesurer le temps d'exécution"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"Temps: {time.time() - start:.2f}s")
        return result
    return wrapper

@timer
def slow_reverse(text: str) -> str:
    """Inverse une chaîne lentement (pour test)"""
    time.sleep(0.5)
    return text[::-1]

async def fetch_strings(urls: list) -> list:
    """Récupère des chaînes depuis une API de manière asynchrone"""
    await asyncio.sleep(1)
    return [f"Data from {url}" for url in urls]
def to_uppercase(text: str) -> str:
    """Convertit une chaîne en majuscules"""
    return text.upper()