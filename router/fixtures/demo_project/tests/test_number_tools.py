import unittest

from number_tools import is_even


class NumberToolTests(unittest.TestCase):
    def test_is_even(self):
        self.assertTrue(is_even(4))
        self.assertFalse(is_even(3))
