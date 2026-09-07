from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_datasets


class ValidateMarketDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_load = validate_datasets.load

    def tearDown(self) -> None:
        validate_datasets.load = self.original_load

    def install_dataset(self, snapshot: dict) -> None:
        marker = {
            "schemaVersion": 1,
            "generatedAt": snapshot["generatedAt"],
            "source": snapshot["source"],
            "status": snapshot["status"],
            "latestTradingDate": snapshot["latestTradingDate"],
            "latestQuoteTimestamp": snapshot["latestQuoteTimestamp"],
            "quoteUniverse": snapshot["stats"]["quoteUniverse"],
            "companies": snapshot["stats"]["companies"],
            "quoteCoverageRatio": snapshot["stats"]["quoteCoverageRatio"],
            "missingQuotes": snapshot["stats"]["missingQuotes"],
            "missingQuoteCodes": snapshot["stats"]["missingQuoteCodes"],
        }

        def fake_load(path: Path) -> dict:
            return marker if path == validate_datasets.MARKET_STATUS else snapshot

        validate_datasets.load = fake_load

    def snapshot(
        self,
        codes: set[str],
        missing: set[str] | None = None,
        status: str | None = None,
    ) -> dict:
        latest = datetime.now(validate_datasets.JST).date().isoformat()
        missing = missing or set()
        quoted_codes = sorted(codes - missing)
        coverage = len(quoted_codes) / len(codes) * 100
        return {
            "schemaVersion": 3,
            "generatedAt": "2026-09-08T00:00:00Z",
            "source": "Yahoo Finance",
            "status": status or ("partial" if missing else "ready"),
            "latestTradingDate": latest,
            "latestQuoteTimestamp": f"{latest}T15:30:00+09:00",
            "quotes": {
                code: {"date": latest, "close": 100.0}
                for code in quoted_codes
            },
            "stats": {
                "quoteUniverse": len(codes),
                "companies": len(quoted_codes),
                "quoteCoverageRatio": round(coverage, 4),
                "missingQuotes": len(missing),
                "missingQuoteCodes": sorted(missing),
            },
        }

    def test_market_accepts_small_declared_partial_gap(self) -> None:
        codes = {f"{code:04d}" for code in range(1000, 1200)}
        snapshot = self.snapshot(codes, {"1199"})
        self.install_dataset(snapshot)

        self.assertEqual(validate_datasets.validate_market(codes), [])

    def test_market_rejects_low_coverage(self) -> None:
        codes = {"1000", "1001", "1002"}
        snapshot = self.snapshot(codes, {"1002"})
        self.install_dataset(snapshot)

        errors = validate_datasets.validate_market(codes)

        self.assertTrue(any("coverage is too low" in error for error in errors), errors)

    def test_market_rejects_ready_status_with_missing_quotes(self) -> None:
        codes = {f"{code:04d}" for code in range(1000, 1200)}
        snapshot = self.snapshot(codes, {"1199"}, status="ready")
        self.install_dataset(snapshot)

        errors = validate_datasets.validate_market(codes)

        self.assertTrue(any("status is not partial" in error for error in errors), errors)

    def test_market_requires_stale_flag_for_older_quote(self) -> None:
        codes = {"1000", "1001"}
        snapshot = self.snapshot(codes)
        snapshot["quotes"]["1001"] = {
            "date": "2026-01-01",
            "close": 100.0,
        }
        self.install_dataset(snapshot)

        errors = validate_datasets.validate_market(codes)

        self.assertTrue(
            any("without stale=true" in error for error in errors),
            errors,
        )

    def test_market_accepts_complete_current_snapshot(self) -> None:
        codes = {"1000", "1001"}
        snapshot = self.snapshot(codes)
        self.install_dataset(snapshot)

        self.assertEqual(validate_datasets.validate_market(codes), [])

    def test_market_status_must_match_snapshot(self) -> None:
        codes = {"1000", "1001"}
        snapshot = self.snapshot(codes)
        self.install_dataset(snapshot)
        original_fake_load = validate_datasets.load

        def fake_load(path: Path) -> dict:
            payload = original_fake_load(path)
            if path == validate_datasets.MARKET_STATUS:
                return {**payload, "generatedAt": "different"}
            return payload

        validate_datasets.load = fake_load

        errors = validate_datasets.validate_market(codes)

        self.assertTrue(
            any("status generatedAt does not match" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
