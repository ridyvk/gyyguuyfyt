from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_annual_dataset


class VerifiedMetricOverrideTests(unittest.TestCase):
    def payload(self) -> dict:
        return {
            "schemaVersion": 1,
            "overrides": {
                "4592": {
                    "periodEnd": "2026-01-31",
                    "previousPeriodEnd": "2025-01-31",
                    "metricKey": "equityRatio",
                    "value": 85.4,
                    "previousValue": 45.1,
                    "documentId": "140120260317583272",
                    "source": "JPX TDnet official earnings summary PDF",
                    "sourceUrl": "https://www2.jpx.co.jp/disc/45920/140120260317583272.pdf",
                    "verifiedAt": "2026-06-22",
                    "evidence": "Page 1",
                }
            },
        }

    def test_exact_period_override_replaces_quarantine(self) -> None:
        records = {
            "4592": {
                "periodEnd": "2026-01-31",
                "metrics": {},
                "quality": {"metricValidationStatus": "quarantined"},
                "quarantine": {
                    "metricValidation": {
                        "metrics": {
                            "equityRatio": {
                                "reason": "value-above-maximum-100"
                            }
                        }
                    }
                },
            }
        }

        applied = finalize_annual_dataset.apply_verified_metric_overrides(
            records,
            self.payload(),
        )

        self.assertEqual(applied, 1)
        self.assertEqual(records["4592"]["metrics"]["equityRatio"]["value"], 85.4)
        self.assertNotIn("quarantine", records["4592"])
        self.assertEqual(
            records["4592"]["quality"]["verifiedOverrides"]["equityRatio"][
                "documentId"
            ],
            "140120260317583272",
        )

    def test_override_is_not_applied_to_a_different_period(self) -> None:
        records = {
            "4592": {
                "periodEnd": "2027-01-31",
                "metrics": {"equityRatio": {"value": 80.0}},
            }
        }

        applied = finalize_annual_dataset.apply_verified_metric_overrides(
            records,
            self.payload(),
        )

        self.assertEqual(applied, 0)
        self.assertEqual(records["4592"]["metrics"]["equityRatio"]["value"], 80.0)


if __name__ == "__main__":
    unittest.main()
