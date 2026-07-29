import unittest

from labels import bracket, prefix


class LabelTests(unittest.TestCase):
    def test_prefix(self):
        self.assertEqual("label: status", prefix("status"))

    def test_bracket(self):
        self.assertEqual("[x]", bracket("x"))
