import unittest

from greeting import greeting


class GreetingTests(unittest.TestCase):
    def test_greeting_is_exact(self):
        self.assertEqual("Welcome, Ada!", greeting("Ada"))


if __name__ == "__main__":
    unittest.main()
