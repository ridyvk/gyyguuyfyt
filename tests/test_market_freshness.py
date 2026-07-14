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

    def test_intraday_payload_uses_market_previous_close_as_change_basis(self) -> None:
        first = int(datetime(2026, 7, 7, 9, 0, tzinfo=JST).timestamp())
        latest = int(datetime(2026, 7, 7, 9, 15, tzinfo=JST).timestamp())
        result = {
            "meta": {
                "chartPreviousClose": 100.0,
                "previousClose": 101.0,
                "regularMarketPrice": 102.5,
                "regularMarketTime": latest,
                "regularMarketVolume": 1200,
            },
            "timestamp": [first, latest],
            "indicators": {
                "quote": [
                    {
                        "close": [101.0, 102.5],
                        "volume": [800, 0],
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
        self.assertEqual(quote["volume"], 1200)
        self.assertEqual(quote["previousClose"], 101.0)
        self.assertEqual(quote["changePercent"], 1.4851)

    def test_intraday_payload_does_not_use_chart_range_baseline(self) -> None:
        range_start = int(datetime(2026, 7, 8, 15, 30, tzinfo=JST).timestamp())
        previous_day = int(datetime(2026, 7, 13, 15, 30, tzinfo=JST).timestamp())
        latest = int(datetime(2026, 7, 14, 15, 15, tzinfo=JST).timestamp())
        result = {
            "meta": {
                "chartPreviousClose": 127.0,
                "previousClose": 230.0,
                "regularMarketPrice": 217.0,
                "regularMarketTime": latest,
                "regularMarketVolume": 18_004_700,
            },
            "timestamp": [range_start, previous_day, latest],
            "indicators": {
                "quote": [
                    {
                        "close": [127.0, 230.0, 217.0],
                        "volume": [100, 200, 300],
                    }
                ]
            },
        }

        quote = quote_payload_from_chart_result(result, INTRADAY_INTERVAL)

        self.assertEqual(quote["previousClose"], 230.0)
        self.assertEqual(quote["changePercent"], -5.6522)

    def test_intraday_payload_derives_previous_session_when_meta_omits_it(self) -> None:
        range_start = int(datetime(2026, 7, 6, 15, 30, tzinfo=JST).timestamp())
        previous_day = int(datetime(2026, 7, 6, 15, 45, tzinfo=JST).timestamp())
        latest = int(datetime(2026, 7, 7, 9, 15, tzinfo=JST).timestamp())
        result = {
            "meta": {
                "chartPreviousClose": 90.0,
                "regularMarketPrice": 102.5,
                "regularMarketTime": latest,
                "regularMarketVolume": 1200,
            },
            "timestamp": [range_start, previous_day, latest],
            "indicators": {
                "quote": [
                    {
                        "close": [99.0, 100.0, 102.5],
                        "volume": [400, 500, 1200],
                    }
                ]
            },
        }

        quote = quote_payload_from_chart_result(result, INTRADAY_INTERVAL)

        self.assertEqual(quote["previousClose"], 100.0)
        self.assertEqual(quote["changePercent"], 2.5)

    def test_intraday_payload_sums_session_bars_when_meta_volume_is_zero(self) -> None:
        previous_day = int(datetime(2026, 7, 6, 15, 15, tzinfo=JST).timestamp())
        first = int(datetime(2026, 7, 7, 9, 0, tzinfo=JST).timestamp())
        latest = int(datetime(2026, 7, 7, 9, 15, tzinfo=JST).timestamp())
        result = {
            "meta": {
                "chartPreviousClose": 100.0,
                "regularMarketPrice": 102.5,
                "regularMarketTime": latest,
                "regularMarketVolume": 0,
            },
            "timestamp": [previous_day, first, latest],
            "indicators": {
                "quote": [
                    {
                        "close": [100.0, 101.0, 102.5],
                        "volume": [5000, 800, 400],
                    }
                ]
            },
        }

        quote = quote_payload_from_chart_result(result, INTRADAY_INTERVAL)

        self.assertEqual(quote["volume"], 1200)

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
        self.assertEqual(quote["volume"], 2000)


if __name__ == "__main__":
    unittest.main()
