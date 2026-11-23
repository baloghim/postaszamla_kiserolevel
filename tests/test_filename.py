from datetime import date
from unittest import TestCase

from postaszamla.filename import make_filename
from postaszamla.models import Cost, Costs


class FilenameTests(TestCase):
    def test_cost_and_service_suffixes(self):
        zero = Cost(0, 0)
        cases = (
            (Costs(Cost(0, 106605), zero, zero, zero), "ellátási"),
            (Costs(Cost(15000, 0), zero, zero, zero), "mukodesi"),
            (Costs(Cost(15000, 40000), zero, zero, zero), "ellátási_mukodesi"),
            (Costs(zero, Cost(0, 176115), zero, zero), "ellátási_ki_be_szallitas"),
            (Costs(zero, zero, Cost(3000, 0), zero), "mukodesi_belfoldi_utankuldes"),
            (Costs(zero, zero, zero, Cost(0, 5000)), "ellátási_fiokberlet"),
            (Costs(Cost(0, 50000), Cost(0, 20000), Cost(3000, 0), Cost(5000, 0)),
             "ellátási_mukodesi_ki_be_szallitas_belfoldi_utankuldes_fiokberlet"),
        )
        for costs, suffix in cases:
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    make_filename(date(2026, 10, 24), date(2026, 10, 31), costs),
                    f"postaszámla_2026.10.24-10.31_{suffix}.docx",
                )

    def test_month_and_year_boundaries(self):
        zero = Cost(0, 0)
        costs = Costs(Cost(0, 5), zero, zero, zero)
        start = date(2026, 10, 24)
        self.assertEqual(make_filename(start, date(2026, 11, 1), costs),
                         "postaszámla_2026.10.24-11.01_ellátási.docx")
        self.assertEqual(make_filename(start, date(2027, 1, 1), costs),
                         "postaszámla_2026.10.24-2027.01.01_ellátási.docx")

    def test_rejects_bad_amounts(self):
        zero = Cost(0, 0)
        start = date(2026, 10, 24)
        for bad in (0, -1, 1.5, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                make_filename(start, start, Costs(Cost(bad, 0), zero, zero, zero))
