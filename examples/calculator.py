# math_lib/calculator.py - Version 2

def add(a: int, b: int, c: int = 0) -> int: 
    return a + b + c

def multiply(a: float, b: float, c: float = 1) -> float:
    return a * b * c

def divide(a, b, precision=2):
    if b == 0:
        raise ValueError("Division par zéro")
    return round(a / b, precision)

def power(a, b):
    return a ** b

def subtract(a, b):
    return a - b
def divide_by_two(a):
    return a / 2
