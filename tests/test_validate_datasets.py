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

    def test_market_requires_full_coverage_and_stale_flags(self) -> None:
        latest = datetime.now(validate_datasets.JST).date().isoformat()

        def fake_load(_: Path) -> dict:
            return {
                "schemaVersion": 3,
                "latestTradingDate": latest,
                "quotes": {
                    "1000": {"date": latest, "close": 100.0},
                    "1001": {"date": "2026-01-01", "close": 100.0},
                },
                "stats": {"companies": 2},
            }

        validate_datasets.load = fake_load

        errors = validate_datasets.validate_market({"1000", "1001", "1002"})

        self.assertTrue(
            any("missing 1 company quote" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("without stale=true" in error for error in errors),
            errors,
        )

    def test_market_accepts_complete_current_snapshot(self) -> None:
        latest = datetime.now(validate_datasets.JST).date().isoformat()

        def fake_load(_: Path) -> dict:
            return {
                "schemaVersion": 3,
                "latestTradingDate": latest,
                "quotes": {
                    "1000": {"date": latest, "close": 100.0},
                    "1001": {
                        "date": "2026-01-01",
                        "close": 100.0,
                        "stale": True,
                    },
                },
                "stats": {"companies": 2},
            }

        validate_datasets.load = fake_load

        self.assertEqual(validate_datasets.validate_market({"1000", "1001"}), [])


if __name__ == "__main__":
    unittest.main()
