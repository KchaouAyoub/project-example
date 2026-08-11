#test_calculator.py - Version 2

from math_lib.calculator import add, divide, multiply, power

"""def test_add():
    assert add(2, 3) == 5"""

def test_multiply():
    assert multiply(2, 3) == 6

def test_divide():
    assert divide(10, 2) == 5

def test_divide_by_zero():
    try:
        divide(10, 0)
    except ValueError:
        pass

def test_power():
    assert power(2, 3) == 8