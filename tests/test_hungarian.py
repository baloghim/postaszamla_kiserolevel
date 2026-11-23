from datetime import date
from unittest import TestCase

from postaszamla.config import parse_date
from postaszamla.dates import hungarian_date
from postaszamla.invoices import format_invoice_numbers, invoice_suffix


class HungarianTextTests(TestCase):
    def test_invoice_order_punctuation_and_suffix(self):
        numbers = ("0001", "0002", "0003", "0004", "0005")
        expected = (
            "0001",
            "0001 és 0002",
            "0001, 0002 és 0003",
            "0001, 0002, 0003 és 0004",
            "0001, 0002, 0003, 0004 és 0005",
        )
        for index, text in enumerate(expected, 1):
            with self.subTest(count=index):
                self.assertEqual(format_invoice_numbers(numbers[:index]), text)
                self.assertEqual(f"száml{invoice_suffix(index)}", "számla" if index == 1 else "számlák")

    def test_suffix_for_each_calendar_day(self):
        endings = (
            "1-jén 2-án 3-án 4-én 5-én 6-án 7-én 8-án 9-én 10-én "
            "11-én 12-én 13-án 14-én 15-én 16-án 17-én 18-án 19-én 20-án "
            "21-én 22-én 23-án 24-én 25-én 26-án 27-én 28-án 29-én 30-án 31-én"
        ).split()
        for day, expected in enumerate(endings, 1):
            with self.subTest(day=day):
                self.assertEqual(hungarian_date(date(2026, 1, day), suffixed=True),
                                 f"2026. január {expected}")

    def test_leap_year_and_letter_date(self):
        leap_day = parse_date("2028-02-29", "Keltezés")
        self.assertEqual(hungarian_date(leap_day), "2028. február 29.")
        self.assertEqual(hungarian_date(leap_day, suffixed=True), "2028. február 29-én")
        with self.assertRaisesRegex(ValueError, "Keltezés"):
            parse_date("2026-02-29", "Keltezés")
