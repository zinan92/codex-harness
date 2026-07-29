import unittest

from number_tools import is_even, is_positive


class NumberToolTests(unittest.TestCase):
    def test_is_even(self):
        self.assertTrue(is_even(4))
        self.assertFalse(is_even(3))

    def test_is_positive(self):
        self.assertTrue(is_positive(1))
        self.assertTrue(is_positive(0.1))
        self.assertFalse(is_positive(0))
        self.assertFalse(is_positive(-1))
