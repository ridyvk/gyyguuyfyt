#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from data_quality import (
    quarantine_invalid_metrics,
    quarantine_misaligned_metric_trends,
    validate_financial_record,
)


def record(metrics: dict, history: list[dict] | None = None) -> dict:
    return {
        "code": "4425",
        "companyName": "Test",
        "documentId": "TEST",
        "filedAt": "2026-06-20T12:00:00+09:00",
        "periodEnd": "2026-03-31",
        "source": "EDINET",
        "metrics": metrics,
        "history": history or [],
    }


class MetricRangeValidationTests(unittest.TestCase):
    def test_validator_rejects_impossible_equity_ratio(self) -> None:
        candidate = record({"equityRatio": {"value": 120.17}})
        self.assertEqual(
            validate_financial_record("4425", candidate, {"4425"}),
            "invalid-metric-range:equityRatio:value-above-maximum-100",
        )

    def test_quarantine_removes_only_invalid_metric(self) -> None:
        candidate = record(
            {
                "equityRatio": {"value": 120.17, "previousValue": 80.0},
                "operatingMargin": {"value": 7.5},
            },
            [{"year": "2026/03", "equityRatio": 120.17, "operatingMargin": 7.5}],
        )
        self.assertEqual(quarantine_invalid_metrics(candidate), 1)
        self.assertNotIn("equityRatio", candidate["metrics"])
        self.assertEqual(candidate["metrics"]["operatingMargin"]["value"], 7.5)
        self.assertNotIn("equityRatio", candidate["history"][0])
        self.assertIn(
            "equityRatio",
            candidate["quarantine"]["metricValidation"]["metrics"],
        )
        self.assertIsNone(validate_financial_record("4425", candidate, {"4425"}))

    def test_quarantine_checks_previous_and_trend_values(self) -> None:
        candidate = record(
            {
                "inventoryGrowth": {
                    "value": 4.0,
                    "previousValue": -101.0,
                    "trend": [-101.0, 4.0],
                },
                "debtRatio": {"value": -0.1},
            }
        )
        self.assertEqual(quarantine_invalid_metrics(candidate), 2)
        self.assertEqual(candidate["metrics"], {})

    def test_misaligned_history_drops_trends_not_metrics(self) -> None:
        candidate = record(
            {
                "operatingMargin": {
                    "value": 5.0,
                    "previousValue": 4.0,
                    "trend": [3.0, 4.0],
                }
            },
            [{"year": "2025/03", "operatingMargin": 4.0}],
        )
        self.assertEqual(quarantine_misaligned_metric_trends(candidate), 1)
        self.assertNotIn("trend", candidate["metrics"]["operatingMargin"])
        self.assertEqual(
            candidate["quarantine"]["historyTrend"]["expectedYear"],
            "2026/03",
        )


if __name__ == "__main__":
    unittest.main()
