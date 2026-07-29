import unittest

from labels import prefix


class LabelTests(unittest.TestCase):
    def test_prefix(self):
        self.assertEqual("label: status", prefix("status"))
