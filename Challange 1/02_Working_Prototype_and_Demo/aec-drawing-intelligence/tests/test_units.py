"""Unit tests for imperial unit and scale parsing."""
import unittest
from aecdi.units import parse_feet_inches, is_dimension, format_feet_inches, parse_scale

class TestUnits(unittest.TestCase):
    def test_parse_feet_inches_standard(self):
        self.assertAlmostEqual(parse_feet_inches("24'-6\""), 24.5)
        self.assertAlmostEqual(parse_feet_inches("30'-0\""), 30.0)
        self.assertAlmostEqual(parse_feet_inches("12'"), 12.0)
        self.assertAlmostEqual(parse_feet_inches("6\""), 0.5)

    def test_parse_feet_inches_fractions(self):
        self.assertAlmostEqual(parse_feet_inches("24'-6 1/2\""), 24.541666666666668)
        self.assertAlmostEqual(parse_feet_inches("1'-0 3/4\""), 1.0625)
        self.assertAlmostEqual(parse_feet_inches("0'-0 1/8\""), 0.010416666666666666)

    def test_format_feet_inches(self):
        self.assertEqual(format_feet_inches(24.5), "24'-6\"")
        self.assertEqual(format_feet_inches(30.0), "30'-0\"")
        self.assertEqual(format_feet_inches(24.541666), "24'-6 1/2\"")

    def test_is_dimension(self):
        self.assertTrue(is_dimension("24'-6\""))
        self.assertTrue(is_dimension("100'-0\""))
        self.assertFalse(is_dimension("ROOM 101"))
        self.assertFalse(is_dimension("DOOR D1"))

    def test_parse_scale(self):
        # 1/8" = 1'-0" -> 0.125 * 72 / 1 = 9.0 pt/ft
        self.assertAlmostEqual(parse_scale("1/8\" = 1'-0\""), 9.0)
        # 1/4" = 1'-0" -> 0.25 * 72 / 1 = 18.0 pt/ft
        self.assertAlmostEqual(parse_scale("1/4\" = 1'-0\""), 18.0)
        # NTS / Not To Scale should return None
        self.assertIsNone(parse_scale("N.T.S."))
        self.assertIsNone(parse_scale("NOT TO SCALE"))

if __name__ == "__main__":
    unittest.main()
