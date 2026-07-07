#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_market_prices import (
    DAILY_INTERVAL,
    INTRADAY_INTERVAL,
    JST,
    mark_market_date_staleness,
    quote_payload_from_chart_result,
)


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

    def test_intraday_payload_keeps_previous_close_as_change_basis(self) -> None:
        first = int(datetime(2026, 7, 7, 9, 0, tzinfo=JST).timestamp())
        latest = int(datetime(2026, 7, 7, 9, 15, tzinfo=JST).timestamp())
        result = {
            "meta": {
                "chartPreviousClose": 100.0,
                "regularMarketPrice": 102.5,
                "regularMarketTime": latest,
                "regularMarketVolume": 1200,
            },
            "timestamp": [first, latest],
            "indicators": {
                "quote": [
                    {
                        "close": [101.0, 102.5],
                        "volume": [800, 1200],
                    }
                ]
            },
        }

        quote = quote_payload_from_chart_result(result, INTRADAY_INTERVAL)

        self.assertEqual(quote["date"], "2026-07-07")
        self.assertEqual(quote["timestamp"], "2026-07-07T09:15:00+09:00")
        self.assertEqual(quote["priceType"], "intraday-15m")
        self.assertEqual(quote["quoteInterval"], "15m")
        self.assertEqual(quote["close"], 102.5)
        self.assertEqual(quote["previousClose"], 100.0)
        self.assertEqual(quote["changePercent"], 2.5)

    def test_daily_payload_uses_regular_market_time_when_newer(self) -> None:
        daily = int(datetime(2026, 7, 7, 9, 0, tzinfo=JST).timestamp())
        close = int(datetime(2026, 7, 7, 15, 30, tzinfo=JST).timestamp())
        result = {
            "meta": {
                "chartPreviousClose": 100.0,
                "regularMarketPrice": 110.0,
                "regularMarketTime": close,
                "regularMarketVolume": 2000,
            },
            "timestamp": [daily],
            "indicators": {
                "quote": [
                    {
                        "close": [108.0],
                        "volume": [1800],
                    }
                ]
            },
        }

        quote = quote_payload_from_chart_result(result, DAILY_INTERVAL)

        self.assertEqual(quote["timestamp"], "2026-07-07T15:30:00+09:00")
        self.assertEqual(quote["priceType"], "regular-market-price")
        self.assertEqual(quote["quoteInterval"], "1d")
        self.assertEqual(quote["close"], 110.0)


if __name__ == "__main__":
    unittest.main()
