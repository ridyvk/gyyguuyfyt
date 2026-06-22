from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_tdnet_financials_strict


class TdnetEquityRatioContextTests(unittest.TestCase):
    def test_duration_equity_ratio_is_available(self) -> None:
        contexts = {
            "CurrentYearDuration": {
                "start": "2025-02-01",
                "end": "2026-01-31",
                "instant": None,
                "dimensions": [],
            }
        }
        facts = {
            "EquityToAssetRatioSummaryOfBusinessResults": [
                (
                    "CurrentYearDuration",
                    0.854,
                    {
                        "tag": "EquityToAssetRatioSummaryOfBusinessResults",
                        "unitRef": "pure",
                    },
                )
            ]
        }

        values = update_tdnet_financials_strict.values_for_instant_or_duration(
            contexts,
            facts,
            update_tdnet_financials_strict.STRICT_TDNET_FACT_NAMES[
                "disclosedEquityRatio"
            ],
        )

        self.assertEqual(values["2026-01-31"], 0.854)

    def test_instant_equity_ratio_wins_for_same_period(self) -> None:
        contexts = {
            "CurrentYearDuration": {
                "start": "2025-02-01",
                "end": "2026-01-31",
                "instant": None,
                "dimensions": [],
            },
            "CurrentYearInstant": {
                "start": None,
                "end": None,
                "instant": "2026-01-31",
                "dimensions": [],
            },
        }
        facts = {
            "EquityToAssetRatio": [
                ("CurrentYearDuration", 0.70, {"unitRef": "pure"}),
                ("CurrentYearInstant", 0.85, {"unitRef": "pure"}),
            ]
        }

        values = update_tdnet_financials_strict.values_for_instant_or_duration(
            contexts,
            facts,
            ("EquityToAssetRatio",),
        )

        self.assertEqual(values["2026-01-31"], 0.85)


if __name__ == "__main__":
    unittest.main()
