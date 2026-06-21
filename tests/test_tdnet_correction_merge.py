#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_tdnet_financials_overlay_strict import merge_correction_record


class CorrectionMergeTests(unittest.TestCase):
    def test_partial_correction_preserves_unmodified_metrics(self) -> None:
        base = {
            "code": "1332",
            "documentId": "BASE",
            "filedAt": "2026-05-10T15:00:00+09:00",
            "periodEnd": "2026-03-31",
            "source": "TDnet",
            "sourceUrl": "base.pdf",
            "metrics": {
                "revenueGrowth": {"value": 2.0},
                "operatingMargin": {"value": 5.0},
                "netMargin": {"value": 3.0},
            },
            "history": [
                {"year": "2025/03", "operatingMargin": 4.0},
                {"year": "2026/03", "operatingMargin": 5.0},
            ],
            "valuation": {"eps": 100.0, "bps": 900.0},
            "quality": {"policy": "strict-full-year-only"},
        }
        correction = {
            **base,
            "documentId": "CORRECTION",
            "filedAt": "2026-06-10T15:00:00+09:00",
            "sourceUrl": "correction.pdf",
            "title": "（訂正）2026年3月期 決算短信",
            "metrics": {
                "operatingMargin": {"value": 5.5},
            },
            "history": [
                {"year": "2026/03", "operatingMargin": 5.5},
            ],
            "valuation": {"eps": 105.0},
        }

        merged = merge_correction_record(base, correction)

        self.assertEqual(merged["metrics"]["revenueGrowth"]["value"], 2.0)
        self.assertEqual(merged["metrics"]["netMargin"]["value"], 3.0)
        self.assertEqual(merged["metrics"]["operatingMargin"]["value"], 5.5)
        self.assertEqual(merged["valuation"], {"eps": 105.0, "bps": 900.0})
        self.assertEqual(merged["history"][-1]["operatingMargin"], 5.5)
        self.assertEqual(
            merged["quality"]["correctionStatus"],
            "merged-with-base-filing",
        )
        self.assertEqual(
            merged["quality"]["correctionBaseDocumentId"],
            "BASE",
        )

    def test_rejects_cross_period_merge(self) -> None:
        base = {"periodEnd": "2025-03-31"}
        correction = {"periodEnd": "2026-03-31"}
        with self.assertRaises(ValueError):
            merge_correction_record(base, correction)


if __name__ == "__main__":
    unittest.main()
