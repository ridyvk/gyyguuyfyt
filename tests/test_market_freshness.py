#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_market_prices import mark_market_date_staleness


class MarketFreshnessTests(unittest.TestCase):
    def test_marks_old_exchange_dates_stale_even_when_fetched(self) -> None:
        quotes = {
            "1000": {"date": "2026-06-19", "stale": False},
            "2000": {"date": "2026-06-18", "stale": False},
            "3000": {"date": "2026-06-17", "stale": True},
        }

        latest, count = mark_market_date_staleness(quotes)

        self.assertEqual(latest, "2026-06-19")
        self.assertEqual(count, 2)
        self.assertFalse(quotes["1000"]["stale"])
        self.assertTrue(quotes["2000"]["stale"])
        self.assertTrue(quotes["3000"]["stale"])


if __name__ == "__main__":
    unittest.main()
