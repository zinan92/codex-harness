import unittest

from text_tools import normalize, shout


class TextToolTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual("clean", normalize("  clean  "))

    def test_shout_uppercase_and_exclamation(self):
        self.assertEqual("HELLO!", shout("  hello  "))

    def test_shout_normalizes_and_forces_single_exclamation(self):
        self.assertEqual("WOW!", shout("  wow!!  "))
