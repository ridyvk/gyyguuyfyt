from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import data_quality


class StandaloneContextSelectionTests(unittest.TestCase):
    def test_non_consolidated_total_actual_context_is_accepted(self) -> None:
        contexts = {
            "CurrentYearDuration_NonConsolidatedMember": {
                "start": "2025-04-01",
                "end": "2026-03-31",
                "instant": None,
                "dimensions": [
                    "ConsolidatedOrNonConsolidatedAxis=NonConsolidatedMember",
                ],
            }
        }
        facts = {
            "NetSales": [
                (
                    "CurrentYearDuration_NonConsolidatedMember",
                    100.0,
                    {"tag": "jppfs_cor:NetSales", "unitRef": "JPY"},
                )
            ]
        }

        selected = data_quality.select_preferred_facts(
            contexts,
            facts,
            ("NetSales",),
            True,
        )["2026-03-31"]

        self.assertEqual(selected["rawValue"], 100.0)
        self.assertEqual(selected["consolidation"], "non-consolidated")

    def test_consolidated_context_beats_non_consolidated_context(self) -> None:
        contexts = {
            "CurrentYearDuration_NonConsolidatedMember": {
                "start": "2025-04-01",
                "end": "2026-03-31",
                "instant": None,
                "dimensions": [
                    "ConsolidatedOrNonConsolidatedAxis=NonConsolidatedMember",
                ],
            },
            "CurrentYearDuration_ConsolidatedMember": {
                "start": "2025-04-01",
                "end": "2026-03-31",
                "instant": None,
                "dimensions": [
                    "ConsolidatedOrNonConsolidatedAxis=ConsolidatedMember",
                ],
            },
        }
        facts = {
            "NetSales": [
                (
                    "CurrentYearDuration_NonConsolidatedMember",
                    100.0,
                    {"tag": "jppfs_cor:NetSales", "unitRef": "JPY"},
                ),
                (
                    "CurrentYearDuration_ConsolidatedMember",
                    300.0,
                    {"tag": "jppfs_cor:NetSales", "unitRef": "JPY"},
                ),
            ]
        }

        selected = data_quality.select_preferred_facts(
            contexts,
            facts,
            ("NetSales",),
            True,
        )["2026-03-31"]

        self.assertEqual(selected["rawValue"], 300.0)
        self.assertEqual(selected["consolidation"], "consolidated")

    def test_non_consolidated_member_is_not_misclassified_as_consolidated(self) -> None:
        context = {
            "start": "2025-04-01",
            "end": "2026-03-31",
            "instant": None,
            "dimensions": [
                "ConsolidatedOrNonConsolidatedAxis=NonConsolidatedMember",
            ],
        }

        self.assertEqual(
            data_quality.consolidation_scope(
                "CurrentYearDuration_NonConsolidatedMember",
                context,
            ),
            "non-consolidated",
        )


if __name__ == "__main__":
    unittest.main()
