"""Test della logica dei rinnovi: python -m unittest test_store"""
import unittest
from datetime import date

import store as S


class RenewalTests(unittest.TestCase):
    def sub(self, **kw):
        s = dict(start="2024-01-31", unit="month", every=1, status="active", price=10.0)
        s.update(kw)
        return s

    def test_month_end_is_kept(self):
        days = [S.occurrence(date(2024, 1, 31), "month", 1, k) for k in range(4)]
        self.assertEqual(days, [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)])

    def test_next_renewal(self):
        self.assertEqual(S.next_renewal(self.sub(), date(2024, 2, 15)), date(2024, 2, 29))
        self.assertEqual(S.next_renewal(self.sub(), date(2024, 3, 31)), date(2024, 3, 31))

    def test_yearly_leap_day(self):
        s = self.sub(start="2024-02-29", unit="year")
        self.assertEqual(S.next_renewal(s, date(2024, 3, 1)), date(2025, 2, 28))
        self.assertEqual(S.next_renewal(s, date(2027, 3, 1)), date(2028, 2, 29))

    def test_cancelled_stops_charges(self):
        s = self.sub(status="cancelled", status_date="2024-06-15")
        self.assertEqual(len(S.charges_between(s, date(2024, 1, 1), date(2024, 12, 31))), 5)
        self.assertIsNone(S.next_renewal(s))

    def test_monthly_cost(self):
        self.assertAlmostEqual(S.monthly_cost(self.sub(price=120, unit="year")), 10)
        self.assertAlmostEqual(S.monthly_cost(self.sub(price=30, every=3)), 10)

    def test_money_and_price(self):
        self.assertEqual(S.money(1234.5), "1.234,50 €")
        self.assertEqual(S.parse_price("1.234,50"), 1234.5)
        self.assertEqual(S.parse_price("13,99"), 13.99)
        self.assertIsNone(S.parse_price(""))


if __name__ == "__main__":
    unittest.main()
