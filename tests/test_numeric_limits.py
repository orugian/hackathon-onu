import unittest
import ml

class NumericLimitTests(unittest.TestCase):
    def test_lab_rejects_numbers_beyond_safe_demonstration_range(self):
        for features in ([1e308, 1, 2], [10**400, 1, 2], [-1e308, 1, 2]):
            with self.subTest(features=str(features)[:80]):
                with self.assertRaises(ValueError):
                    ml.predict(features)

if __name__ == '__main__': unittest.main()
