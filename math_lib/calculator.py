# math_lib/calculator.py - Version 2

def add(a, b, c=0, d=0):
    return (a + b + c + d)

def multiply(a, b,  c=1):
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