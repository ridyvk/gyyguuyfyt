from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import data_quality
import finalize_annual_dataset
import update_edinet_financials
import update_edinet_financials_batched
import update_market_prices


def record(code: str, period_end: str = "2026-03-31") -> dict:
    return {
        "code": code,
        "companyName": "Example",
        "documentId": "DOC1",
        "documentType": "AnnualSecuritiesReport",
        "filedAt": "2026-06-20T10:00:00+09:00",
        "periodEnd": period_end,
        "source": "EDINET",
        "sourceUrl": "https://example.test/filing",
        "metrics": {"revenueGrowth": {"value": 5.0}},
        "history": [],
    }


class DateAndRecordValidationTests(unittest.TestCase):
    def test_none_string_is_not_a_date(self) -> None:
        self.assertFalse(data_quality.is_iso_date("None"))
        self.assertFalse(data_quality.is_iso_date(None))
        self.assertTrue(data_quality.is_iso_date("2026-03-31"))

    def test_period_is_more_important_than_submission_time(self) -> None:
        annual = {
            "periodEnd": "2026-03-31",
            "submitDateTime": "2026-06-01T10:00:00",
            "docID": "ANNUAL",
        }
        old_correction = {
            "periodEnd": "2025-03-31",
            "submitDateTime": "2026-06-20T10:00:00",
            "docID": "CORRECTION",
        }
        self.assertGreater(
            data_quality.filing_order_key(annual),
            data_quality.filing_order_key(old_correction),
        )

    def test_invalid_and_foreign_records_are_dropped(self) -> None:
        valid, failures = finalize_annual_dataset.validated_records(
            {
                "1000": record("1000"),
                "1001": record("1001", "None"),
                "9999": record("9999"),
            },
            {"1000", "1001"},
        )
        self.assertEqual(set(valid), {"1000"})
        self.assertEqual(failures["invalid-period-end"], 1)
        self.assertEqual(failures["not-in-company-master"], 1)

    def test_exact_period_lookup_never_falls_back_to_an_older_year(self) -> None:
        self.assertIsNone(
            update_edinet_financials.at(
                {"2025-03-31": 100.0},
                "2026-03-31",
            )
        )


class RoeCalculationTests(unittest.TestCase):
    def test_current_and_previous_roe_both_use_average_equity(self) -> None:
        profits = {
            "2024-12-31": 2_238_000_000.0,
            "2025-12-31": 3_464_000_000.0,
        }
        equities = {
            "2023-12-31": 7_200_000_000.0,
            "2024-12-31": 12_100_000_000.0,
            "2025-12-31": 17_433_000_000.0,
        }
        current_period = "2025-12-31"
        previous_period = update_edinet_financials.period_before(
            profits,
            current_period,
        )

        current_roe = update_edinet_financials.roe_for_period(
            profits,
            equities,
            current_period,
        )
        previous_roe = update_edinet_financials.roe_for_period(
            profits,
            equities,
            previous_period,
        )

        self.assertEqual(round(current_roe or 0, 1), 23.5)
        self.assertEqual(round(previous_roe or 0, 1), 23.2)
        self.assertEqual(round((current_roe or 0) - (previous_roe or 0), 1), 0.3)

    def test_previous_roe_is_not_based_on_closing_equity_only(self) -> None:
        profits = {"2024-03-31": 200.0}
        equities = {
            "2023-03-31": 1_000.0,
            "2024-03-31": 1_200.0,
        }
        roe = update_edinet_financials.roe_for_period(
            profits,
            equities,
            "2024-03-31",
        )
        self.assertAlmostEqual(roe or 0, 200 / 1_100 * 100)
        self.assertNotAlmostEqual(roe or 0, 200 / 1_200 * 100)


class XbrlContextTests(unittest.TestCase):
    def test_segment_context_cannot_beat_company_total(self) -> None:
        contexts = {
            "CurrentYearDuration": {
                "start": "2025-04-01",
                "end": "2026-03-31",
                "instant": None,
                "dimensions": [],
            },
            "CurrentYearSegment": {
                "start": "2025-04-01",
                "end": "2026-03-31",
                "instant": None,
                "dimensions": [
                    "ConsolidatedOrNonConsolidatedAxis=ConsolidatedMember",
                    "OperatingSegmentsAxis=CloudMember",
                ],
            },
        }
        facts = {
            "NetSales": [
                ("CurrentYearDuration", 100.0),
                ("CurrentYearSegment", 900.0),
            ]
        }
        values = data_quality.select_preferred_values(
            contexts, facts, ("NetSales",), True
        )
        self.assertEqual(values, {"2026-03-31": 100.0})

    def test_fact_name_order_is_respected(self) -> None:
        contexts = {
            "CurrentYearDuration": {
                "start": "2025-04-01",
                "end": "2026-03-31",
                "instant": None,
                "dimensions": [],
            }
        }
        facts = {
            "NetSales": [("CurrentYearDuration", 100.0)],
            "Revenue": [("CurrentYearDuration", 200.0)],
        }
        values = data_quality.select_preferred_values(
            contexts, facts, ("NetSales", "Revenue"), True
        )
        self.assertEqual(values["2026-03-31"], 100.0)


class BatchedMigrationTests(unittest.TestCase):
    def test_old_model_records_are_not_marked_as_processed(self) -> None:
        old_record = record("1000")
        old_record["documentId"] = "OLD"
        current_record = record("1001")
        current_record["documentId"] = "CURRENT"
        current_record["quality"] = {
            "dataModelVersion": update_edinet_financials_batched.DATA_MODEL_VERSION
        }
        processed = update_edinet_financials_batched.collect_processed_doc_ids(
            {"stats": {}},
            {"1000": old_record, "1001": current_record},
            False,
        )
        self.assertNotIn("OLD", processed)
        self.assertIn("CURRENT", processed)


class MarketMergeTests(unittest.TestCase):
    def test_market_merge_drops_extra_and_expired_quotes(self) -> None:
        previous = {
            "1000": {"date": "2026-06-19", "close": 100},
            "1001": {"date": "2026-05-01", "close": 200},
            "9999": {"date": "2026-06-19", "close": 300},
        }
        merged, fallback_count, stale_dropped = update_market_prices.merge_quotes(
            ["1000", "1001"], previous, {}, date(2026, 6, 20)
        )
        self.assertEqual(set(merged), {"1000"})
        self.assertTrue(merged["1000"]["stale"])
        self.assertEqual(fallback_count, 1)
        self.assertEqual(stale_dropped, 1)


class DeliveryTests(unittest.TestCase):
    def test_source_index_has_no_runtime_cdn_bootstrap(self) -> None:
        source = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("api.github.com", source)
        self.assertNotIn("cdn.jsdelivr.net", source)
        self.assertIn('/src/main.tsx', source)

    def test_only_deploy_workflow_deploys_pages(self) -> None:
        workflows = ROOT / ".github/workflows"
        deploy = (workflows / "deploy-pages.yml").read_text(encoding="utf-8")
        financial = (workflows / "update-financials.yml").read_text(encoding="utf-8")
        market = (workflows / "update-market.yml").read_text(encoding="utf-8")
        company_master = (workflows / "update-company-master.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("actions/deploy-pages", deploy)
        self.assertNotIn("actions/deploy-pages", financial)
        self.assertNotIn("actions/deploy-pages", market)
        self.assertIn("Update annual financials", deploy)
        self.assertIn("Update market prices", deploy)
        self.assertIn("Update JPX company master", financial)
        self.assertIn("Update JPX company master", market)
        self.assertIn("ref: main", company_master)


if __name__ == "__main__":
    unittest.main()
