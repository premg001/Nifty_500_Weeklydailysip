import unittest
from unittest.mock import patch

import pandas as pd

from scanner import simulate


class SimulateTouchTests(unittest.TestCase):
    def test_low_crossing_line_signals_even_when_candle_high_is_below_it(self):
        dates = pd.to_datetime(["2025-01-03", "2025-01-06", "2025-01-07"])
        frame = pd.DataFrame(
            {
                "Low": [110.0, 90.0, 95.0],
                "High": [115.0, 95.0, 105.0],
            },
            index=dates,
        )

        with patch("scanner.weekly_pivots", return_value=[(dates[0], 100.0)]):
            _, buys, _ = simulate(frame, start_date=None)

        self.assertEqual(
            buys,
            [{"date": "2025-01-06", "price": 100.0, "qty": 100}],
        )

    def test_line_is_only_used_on_first_low_crossing(self):
        dates = pd.to_datetime(["2025-01-03", "2025-01-06"])
        frame = pd.DataFrame(
            {
                "Low": [110.0, 100.0],
                "High": [115.0, 105.0],
            },
            index=dates,
        )

        with patch("scanner.weekly_pivots", return_value=[(dates[0], 100.0)]):
            _, buys, _ = simulate(frame, start_date=None)

        self.assertEqual(len(buys), 1)
        self.assertEqual(buys[0]["date"], "2025-01-06")

    def test_highest_crossed_line_buys_and_other_touched_lines_are_ignored(self):
        dates = pd.to_datetime(["2025-01-03", "2025-01-06"])
        frame = pd.DataFrame(
            {
                "Low": [110.0, 90.0],
                "High": [115.0, 95.0],
            },
            index=dates,
        )

        with patch(
            "scanner.weekly_pivots",
            return_value=[(dates[0], 95.0), (dates[0], 100.0)],
        ):
            remaining_lines, buys, ignored = simulate(frame, start_date=None)

        self.assertEqual(buys[0]["price"], 100.0)
        self.assertEqual(ignored, 1)
        self.assertEqual(remaining_lines, [])

    def test_out_of_range_touch_consumes_line_without_counting_a_buy(self):
        dates = pd.to_datetime(["2025-01-03", "2025-01-06", "2025-01-07"])
        frame = pd.DataFrame(
            {
                "Low": [110.0, 90.0, 80.0],
                "High": [115.0, 95.0, 85.0],
            },
            index=dates,
        )

        with patch("scanner.weekly_pivots", return_value=[(dates[0], 100.0)]):
            remaining_lines, buys, ignored = simulate(
                frame, start_date="2025-01-07"
            )

        self.assertEqual(buys, [])
        self.assertEqual(ignored, 0)
        self.assertEqual(remaining_lines, [])

    def test_buy_price_keeps_full_precision_for_position_calculations(self):
        dates = pd.to_datetime(["2025-01-03", "2025-01-06"])
        frame = pd.DataFrame(
            {
                "Low": [110.0, 100.0],
                "High": [115.0, 105.0],
            },
            index=dates,
        )

        with patch(
            "scanner.weekly_pivots",
            return_value=[(dates[0], 100.123456)],
        ):
            _, buys, _ = simulate(frame, start_date=None)

        self.assertAlmostEqual(buys[0]["price"], 100.123456)


if __name__ == "__main__":
    unittest.main()
