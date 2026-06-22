from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import reconcile_financial_sources


class RecoveredMetricQuarantineTests(unittest.TestCase):
    def test_tdnet_only_metric_clears_old_range_quarantine(self) -> None:
        edinet = {
            "code": "4592",
            "source": "EDINET",
            "documentId": "EDINET1",
            "filedAt": "2026-03-17T09:00:00+09:00",
            "periodEnd": "2026-01-31",
            "sourceUrl": "https://example.test/edinet",
            "metrics": {"roe": {"value": 10.0}},
            "history": [],
            "quarantine": {
                "metricValidation": {
                    "policy": "hard-accounting-ranges-v1",
                    "metrics": {
                        "equityRatio": {
                            "reason": "value-above-maximum-100",
                            "metric": {"value": 124.61},
                        }
                    },
                }
            },
        }
        tdnet = {
            "code": "4592",
            "source": "TDnet",
            "documentId": "TDNET1",
            "filedAt": "2026-03-17T15:00:00+09:00",
            "periodEnd": "2026-01-31",
            "sourceUrl": "https://example.test/tdnet",
            "metrics": {
                "equityRatio": {
                    "value": 85.4,
                    "previousValue": 45.1,
                    "provenance": {
                        "formula": "disclosedEquityRatio",
                        "sourceFacts": [
                            {
                                "role": "disclosedEquityRatio.current",
                                "rawValue": 0.854,
                            }
                        ],
                    },
                }
            },
            "history": [],
        }

        result = reconcile_financial_sources.reconcile_same_period(
            edinet,
            tdnet,
            checked_at="2026-06-22T13:00:00Z",
        )

        self.assertIsNotNone(result)
        self.assertEqual(edinet["metrics"]["equityRatio"]["value"], 85.4)
        self.assertNotIn("quarantine", edinet)

    def test_unrecovered_metric_keeps_quarantine(self) -> None:
        record = {
            "metrics": {},
            "quarantine": {
                "metricValidation": {
                    "metrics": {"equityRatio": {"reason": "invalid"}}
                }
            },
        }

        reconcile_financial_sources.clear_metric_validation_quarantine(
            record,
            "roe",
        )

        self.assertIn(
            "equityRatio",
            record["quarantine"]["metricValidation"]["metrics"],
        )


if __name__ == "__main__":
    unittest.main()
