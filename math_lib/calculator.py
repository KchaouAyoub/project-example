# math_lib/calculator.py - Version 2

def add(a, b, c=0):
    """Additionne deux ou trois nombres"""
    return a + b + c

def multiply(a, b):
    """Multiplie deux nombres"""
    return a * b

def divide(a, b, precision=2):
    """Divise a par b avec une précision donnée"""
    if b == 0:
        raise ValueError("Division par zéro")
    return round(a / b, precision)

def power(a, b):
    """Élève a à la puissance b"""
    return a ** b