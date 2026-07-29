import unittest

from text_tools import normalize


class TextToolTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual("clean", normalize("  clean  "))
