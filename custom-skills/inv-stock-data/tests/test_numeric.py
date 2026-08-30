import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "_shared"))

from numeric import parse_number, parse_percent


class NumericParsingTest(unittest.TestCase):
    def test_parse_number_with_chinese_units(self):
        self.assertEqual(parse_number("104.13亿"), 10413000000.0)
        self.assertEqual(parse_number("2.3万"), 23000.0)
        self.assertEqual(parse_number("1.2万亿"), 1200000000000.0)
        self.assertEqual(parse_number("38.5%"), 38.5)
        self.assertIsNone(parse_number(True))

    def test_parse_percent(self):
        self.assertEqual(parse_percent("48.01%"), 48.01)
        self.assertEqual(parse_percent(0.4801), 48.01)
        self.assertEqual(parse_percent(48.01), 48.01)


if __name__ == "__main__":
    unittest.main()
