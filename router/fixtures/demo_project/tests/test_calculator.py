import unittest

from calculator import increment


class CalculatorTests(unittest.TestCase):
    def test_increment(self):
        self.assertEqual(3, increment(2))
