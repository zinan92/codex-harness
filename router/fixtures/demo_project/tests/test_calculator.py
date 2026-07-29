import unittest

from calculator import double, increment


class CalculatorTests(unittest.TestCase):
    def test_increment(self):
        self.assertEqual(3, increment(2))

    def test_double(self):
        self.assertEqual(6, double(3))
