from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import data_quality
import finalize_annual_dataset
import reconcile_financial_sources
import update_edinet_financials
import update_edinet_financials_batched
import update_market_prices
import update_tdnet_financials_overlay_strict
import update_tdnet_financials_strict


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

    def test_missing_metrics_is_classified_as_unusable_not_failed(self) -> None:
        self.assertTrue(data_quality.is_unusable_record_validation("missing-metrics"))
        self.assertTrue(
            data_quality.is_unusable_record_validation(
                "no metrics extracted: contexts=112, numericFacts=600"
            )
        )
        self.assertFalse(data_quality.is_unusable_record_validation("invalid-period-end"))
        self.assertFalse(data_quality.is_unusable_record_validation(None))

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


class RoeQuarantineTests(unittest.TestCase):
    def test_v5_edinet_roe_is_quarantined_without_dropping_company(self) -> None:
        stale = record("5987", "2025-06-30")
        stale["metrics"]["roe"] = {
            "value": 0.0,
            "previousValue": -6.96,
        }
        stale["history"] = [
            {"year": "2024/06", "roe": -6.96},
            {"year": "2025/06", "roe": 0.0},
        ]
        stale["quality"] = {"dataModelVersion": 5}

        changed = finalize_annual_dataset.quarantine_untrusted_roe(stale)

        self.assertTrue(changed)
        self.assertNotIn("roe", stale["metrics"])
        self.assertTrue(all("roe" not in point for point in stale["history"]))
        self.assertEqual(
            stale["quality"]["roeStatus"],
            "quarantined-stale-model",
        )

    def test_v6_edinet_roe_remains_available(self) -> None:
        current = record("1000")
        current["metrics"]["roe"] = {"value": 12.5}
        current["quality"] = {"dataModelVersion": 6}

        changed = finalize_annual_dataset.quarantine_untrusted_roe(current)

        self.assertFalse(changed)
        self.assertEqual(current["metrics"]["roe"]["value"], 12.5)

    def test_tdnet_roe_is_not_quarantined_by_edinet_model_rule(self) -> None:
        tdnet = record("1000")
        tdnet["source"] = "TDnet"
        tdnet["documentType"] = "FullYearEarnings"
        tdnet["metrics"]["roe"] = {"value": 8.4}

        changed = finalize_annual_dataset.quarantine_untrusted_roe(tdnet)

        self.assertFalse(changed)
        self.assertEqual(tdnet["metrics"]["roe"]["value"], 8.4)


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

    def test_disclosed_roe_takes_precedence_over_recalculation(self) -> None:
        disclosed = {
            "2024-12-31": 0.232,
            "2025-12-31": 0.235,
        }
        profits = {
            "2024-12-31": 2_238_000_000.0,
            "2025-12-31": 3_464_000_000.0,
        }
        equities = {
            "2023-12-31": 7_200_000_000.0,
            "2024-12-31": 12_100_000_000.0,
            "2025-12-31": 17_433_000_000.0,
        }

        current = update_edinet_financials.disclosed_or_calculated_roe(
            disclosed, profits, equities, "2025-12-31"
        )
        previous = update_edinet_financials.disclosed_or_calculated_roe(
            disclosed, profits, equities, "2024-12-31"
        )

        self.assertAlmostEqual(current or 0, 23.5)
        self.assertAlmostEqual(previous or 0, 23.2)
        self.assertEqual(round((current or 0) - (previous or 0), 1), 0.3)

    def test_disclosed_roe_falls_back_to_recalculation(self) -> None:
        profits = {"2025-03-31": 120.0}
        equities = {
            "2024-03-31": 900.0,
            "2025-03-31": 1_100.0,
        }
        roe = update_edinet_financials.disclosed_or_calculated_roe(
            {}, profits, equities, "2025-03-31"
        )
        self.assertEqual(roe, 12.0)

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


class SourceReconciliationTests(unittest.TestCase):
    def tdnet_record(self) -> dict:
        return {
            "code": "1000",
            "companyName": "Example",
            "documentId": "TDNET1",
            "documentType": "FullYearEarnings",
            "filedAt": "2026-05-10T15:00:00+09:00",
            "periodEnd": "2026-03-31",
            "source": "TDnet",
            "sourceUrl": "https://example.test/tdnet",
            "metrics": {},
            "history": [],
        }

    def test_matching_metrics_keep_edinet_and_prefer_disclosed_tdnet_roe(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {
            "operatingMargin": {"value": 10.0, "previousValue": 9.0},
            "roe": {
                "value": 12.2,
                "previousValue": 11.0,
                "provenance": {
                    "sourceFacts": [{"role": "profit.current"}]
                },
            },
        }
        edinet["history"] = [
            {"year": "2025/03", "roe": 11.0},
            {"year": "2026/03", "roe": 12.2},
        ]
        tdnet = self.tdnet_record()
        tdnet["metrics"] = {
            "operatingMargin": {"value": 10.2, "previousValue": 9.1},
            "roe": {
                "value": 12.4,
                "previousValue": 11.2,
                "provenance": {
                    "sourceFacts": [{"role": "disclosedRoe.current"}]
                },
            },
        }
        tdnet["history"] = [
            {"year": "2025/03", "roe": 11.2},
            {"year": "2026/03", "roe": 12.4},
        ]

        summary = reconcile_financial_sources.reconcile_same_period(
            edinet,
            tdnet,
            checked_at="2026-06-20T00:00:00Z",
        )

        self.assertIsNotNone(summary)
        self.assertEqual(summary.matched, 2)
        self.assertEqual(summary.quarantined, 0)
        self.assertEqual(edinet["metrics"]["operatingMargin"]["value"], 10.0)
        self.assertEqual(edinet["metrics"]["roe"]["value"], 12.4)
        self.assertEqual([point["roe"] for point in edinet["history"]], [11.2, 12.4])
        self.assertEqual(edinet["reconciliation"]["status"], "matched")
        self.assertNotIn("quarantine", edinet)

    def test_disclosed_edinet_roe_is_not_compared_with_calculated_tdnet_roe(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {
            "roe": {
                "value": 7.8,
                "previousValue": 19.3,
                "provenance": {
                    "sourceFacts": [{"role": "disclosedRoe.current"}]
                },
            }
        }
        tdnet = self.tdnet_record()
        tdnet["metrics"] = {
            "roe": {
                "value": 7.98,
                "previousValue": 18.13,
                "provenance": {"sourceFacts": [{"role": "profit.current"}]},
            }
        }

        summary = reconcile_financial_sources.reconcile_same_period(edinet, tdnet)

        self.assertEqual(summary.quarantined, 0)
        self.assertEqual(edinet["metrics"]["roe"]["value"], 7.8)
        result = edinet["reconciliation"]["metrics"]["roe"]
        self.assertEqual(result["status"], "definition-difference")
        self.assertEqual(result["selectedSource"], "EDINET")

    def test_disclosed_equity_ratio_beats_calculated_ratio(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {
            "equityRatio": {
                "value": 48.7,
                "provenance": {
                    "sourceFacts": [
                        {"role": "disclosedEquityRatio.current"}
                    ]
                },
            }
        }
        tdnet = self.tdnet_record()
        tdnet["metrics"] = {
            "equityRatio": {
                "value": 45.17,
                "provenance": {"sourceFacts": [{"role": "equity.current"}]},
            }
        }

        summary = reconcile_financial_sources.reconcile_same_period(edinet, tdnet)

        self.assertEqual(summary.quarantined, 0)
        self.assertEqual(edinet["metrics"]["equityRatio"]["value"], 48.7)

    def test_different_cash_concepts_are_not_compared_as_net_cash(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {
            "netCash": {
                "value": -624.92,
                "provenance": {
                    "sourceFacts": [
                        {
                            "role": "cash.current",
                            "concept": "CashAndCashEquivalents",
                        }
                    ]
                },
            }
        }
        tdnet = self.tdnet_record()
        tdnet["metrics"] = {
            "netCash": {
                "value": -597.31,
                "provenance": {
                    "sourceFacts": [
                        {"role": "cash.current", "concept": "CashAndDeposits"}
                    ]
                },
            }
        }

        summary = reconcile_financial_sources.reconcile_same_period(edinet, tdnet)

        self.assertEqual(summary.quarantined, 0)
        self.assertEqual(edinet["metrics"]["netCash"]["value"], -624.92)

    def test_previous_mismatch_does_not_remove_matching_current_value(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {
            "roe": {"value": -203.54, "previousValue": -105.7, "trend": [1, 2]}
        }
        edinet["history"] = [{"year": "2026/03", "roe": -203.54}]
        tdnet = self.tdnet_record()
        tdnet["metrics"] = {"roe": {"value": -203.54, "previousValue": -88.63}}

        summary = reconcile_financial_sources.reconcile_same_period(edinet, tdnet)

        self.assertEqual(summary.quarantined, 0)
        self.assertEqual(edinet["metrics"]["roe"]["value"], -203.54)
        self.assertNotIn("previousValue", edinet["metrics"]["roe"])
        self.assertNotIn("trend", edinet["metrics"]["roe"])
        self.assertNotIn("roe", edinet["history"][0])
        self.assertEqual(
            edinet["reconciliation"]["metrics"]["roe"]["status"],
            "matched-current-only",
        )

    def test_stored_v1_definition_quarantine_is_repaired(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {}
        edinet["quarantine"] = {
            "sourceReconciliation": {
                "metrics": {
                    "roe": {
                        "edinet": {
                            "value": 7.8,
                            "provenance": {
                                "sourceFacts": [
                                    {"role": "disclosedRoe.current"}
                                ]
                            },
                        },
                        "tdnet": {
                            "value": 7.98,
                            "provenance": {
                                "sourceFacts": [{"role": "profit.current"}]
                            },
                        },
                    }
                }
            }
        }
        edinet["reconciliation"] = {
            "modelVersion": 1,
            "metrics": {"roe": {"status": "quarantined"}},
            "quarantinedMetrics": ["roe"],
        }

        repaired = reconcile_financial_sources.repair_stored_definition_quarantines(
            edinet
        )

        self.assertEqual(repaired, 1)
        self.assertEqual(edinet["metrics"]["roe"]["value"], 7.8)
        self.assertEqual(edinet["reconciliation"]["modelVersion"], 2)
        self.assertEqual(edinet["reconciliation"]["quarantinedMetrics"], [])
        self.assertNotIn("quarantine", edinet)

    def test_mismatch_quarantines_only_the_disputed_metric(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {
            "operatingMargin": {
                "value": 10.0,
                "provenance": {"formula": "edinet", "sourceFacts": []},
            },
            "netMargin": {"value": 4.0},
        }
        edinet["history"] = [
            {"year": "2026/03", "operatingMargin": 10.0, "netMargin": 4.0}
        ]
        tdnet = self.tdnet_record()
        tdnet["metrics"] = {
            "operatingMargin": {
                "value": 20.0,
                "provenance": {"formula": "tdnet", "sourceFacts": []},
            },
            "netMargin": {"value": 4.1},
        }

        summary = reconcile_financial_sources.reconcile_same_period(
            edinet,
            tdnet,
            checked_at="2026-06-20T00:00:00Z",
        )

        self.assertEqual(summary.quarantined, 1)
        self.assertNotIn("operatingMargin", edinet["metrics"])
        self.assertEqual(edinet["metrics"]["netMargin"]["value"], 4.0)
        self.assertNotIn("operatingMargin", edinet["history"][0])
        isolated = edinet["quarantine"]["sourceReconciliation"]["metrics"]
        self.assertEqual(isolated["operatingMargin"]["edinet"]["value"], 10.0)
        self.assertEqual(isolated["operatingMargin"]["tdnet"]["value"], 20.0)
        self.assertEqual(edinet["quality"]["reconciliationStatus"], "quarantined")

    def test_fully_quarantined_company_is_retained_for_audit(self) -> None:
        edinet = record("1000")
        edinet["metrics"] = {"operatingMargin": {"value": 10.0}}
        tdnet = self.tdnet_record()
        tdnet["metrics"] = {"operatingMargin": {"value": 20.0}}

        reconcile_financial_sources.reconcile_same_period(
            edinet,
            tdnet,
            checked_at="2026-06-20T00:00:00Z",
        )

        self.assertEqual(edinet["metrics"], {})
        self.assertIsNone(
            data_quality.validate_financial_record("1000", edinet, {"1000"})
        )

    def test_different_periods_are_not_reconciled(self) -> None:
        edinet = record("1000", "2026-03-31")
        tdnet = self.tdnet_record()
        tdnet["periodEnd"] = "2025-03-31"

        self.assertIsNone(
            reconcile_financial_sources.reconcile_same_period(edinet, tdnet)
        )
        self.assertNotIn("reconciliation", edinet)

    def test_reconciliation_totals_count_only_compared_results(self) -> None:
        records = {
            "1000": {
                "reconciliation": {
                    "metrics": {
                        "roe": {"status": "matched"},
                        "netMargin": {"status": "quarantined"},
                        "netCash": {"status": "edinet-only"},
                    }
                }
            }
        }

        self.assertEqual(
            reconcile_financial_sources.reconciliation_totals(records),
            {
                "sourceReconciliationCompanies": 1,
                "sourceMatchedMetrics": 1,
                "sourceQuarantinedMetrics": 1,
            },
        )

    def test_reconciliation_dispute_details_are_bounded_and_actionable(self) -> None:
        records = {
            "1000": {
                "companyName": "Example",
                "periodEnd": "2026-03-31",
                "quarantine": {
                    "sourceReconciliation": {
                        "metrics": {
                            "operatingMargin": {
                                "reason": "edinet-tdnet-value-mismatch",
                                "comparison": {"value": {"matched": False}},
                                "edinet": {"value": 10.0},
                                "tdnet": {"value": 20.0},
                            }
                        }
                    }
                },
            }
        }

        details = reconcile_financial_sources.reconciliation_dispute_details(records)

        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["code"], "1000")
        self.assertEqual(details[0]["metric"], "operatingMargin")
        self.assertEqual(details[0]["edinetValue"], 10.0)
        self.assertEqual(details[0]["tdnetValue"], 20.0)


class TdnetRoeDisclosureTests(unittest.TestCase):
    def test_disclosed_roe_fact_is_parsed_as_a_duration_value(self) -> None:
        self.assertIn(
            "RateOfReturnOnEquitySummaryOfBusinessResults",
            update_tdnet_financials_strict.STRICT_TDNET_FACT_NAMES["disclosedRoe"],
        )
        self.assertIn(
            "disclosedRoe",
            update_tdnet_financials_strict.DURATION_KEYS,
        )

    def test_tdnet_disclosed_roe_is_already_a_percentage(self) -> None:
        value = update_tdnet_financials_strict.disclosed_or_calculated_tdnet_roe(
            {"2025-12-31": 23.5},
            {"2025-12-31": 100.0},
            {"2024-12-31": 400.0, "2025-12-31": 500.0},
            "2025-12-31",
        )
        self.assertEqual(value, 23.5)

    def test_tdnet_disclosed_equity_ratio_is_supported_and_normalized(self) -> None:
        names = update_tdnet_financials_strict.STRICT_TDNET_FACT_NAMES[
            "disclosedEquityRatio"
        ]
        self.assertIn("EquityToAssetRatio", names)
        self.assertIn("EquityToAssetRatioSummaryOfBusinessResults", names)
        self.assertNotIn(
            "disclosedEquityRatio",
            update_tdnet_financials_strict.DURATION_KEYS,
        )
        self.assertEqual(update_tdnet_financials_strict.disclosed_percent(0.667), 66.7)
        self.assertEqual(update_tdnet_financials_strict.disclosed_percent(66.7), 66.7)

    def test_tdnet_equity_fallback_prefers_net_assets_to_shareholders_equity(self) -> None:
        names = update_tdnet_financials_strict.STRICT_TDNET_FACT_NAMES["equity"]
        self.assertLess(names.index("NetAssets"), names.index("ShareholdersEquity"))

    def test_one_impossible_metric_can_be_quarantined_without_losing_record(self) -> None:
        tdnet = {
            "code": "7777",
            "companyName": "Example",
            "documentId": "TDNET1",
            "documentType": "FullYearEarnings",
            "filedAt": "2026-06-11T16:00:00+09:00",
            "periodEnd": "2026-04-30",
            "source": "TDnet",
            "sourceUrl": "https://example.test/tdnet",
            "metrics": {
                "operatingMargin": {"value": 12.26},
                "equityRatio": {"value": 122.51},
            },
            "history": [],
        }

        quarantined = data_quality.quarantine_invalid_metrics(tdnet)

        self.assertEqual(quarantined, 1)
        self.assertIn("operatingMargin", tdnet["metrics"])
        self.assertNotIn("equityRatio", tdnet["metrics"])
        self.assertIsNone(
            data_quality.validate_financial_record("7777", tdnet, {"7777"})
        )

    def test_backfill_candidates_are_bounded_and_code_ordered(self) -> None:
        today = datetime.now(timezone.utc)
        old = (today - timedelta(days=60)).isoformat()
        recent = (today - timedelta(days=1)).isoformat()
        filings = {
            "1301": {"code": "1301", "filedAt": old},
            "1500": {"code": "1500", "filedAt": old},
            "146A": {"code": "146A", "filedAt": old},
            "1400": {"code": "1400", "filedAt": recent},
        }
        records = {
            code: {
                "source": "EDINET",
                "quality": {},
            }
            for code in filings
        }

        candidates = update_tdnet_financials_overlay_strict.select_candidates(
            filings,
            records,
            lookback_days=31,
            backfill_limit=1,
            max_documents=10,
        )

        self.assertEqual(
            [candidate["code"] for candidate in candidates],
            ["1400", "146A"],
        )

    def test_backfill_advances_past_previously_attempted_documents(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        filings = {
            "130A": {"code": "130A", "filedAt": old, "documentId": "DOC130"},
            "140A": {"code": "140A", "filedAt": old, "documentId": "DOC140"},
            "146A": {"code": "146A", "filedAt": old, "documentId": "DOC146"},
        }
        records = {
            code: {"source": "EDINET", "quality": {}}
            for code in filings
        }
        attempted = {"DOC130", "DOC140"}

        candidates = update_tdnet_financials_overlay_strict.select_candidates(
            filings,
            records,
            lookback_days=31,
            backfill_limit=1,
            max_documents=10,
            attempted_document_ids=attempted,
        )

        self.assertEqual([candidate["code"] for candidate in candidates], ["146A"])
        self.assertEqual(attempted, {"DOC130", "DOC140"})

    def test_backfill_retries_after_all_documents_were_attempted(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        filings = {
            "130A": {"code": "130A", "filedAt": old, "documentId": "DOC130"},
            "146A": {"code": "146A", "filedAt": old, "documentId": "DOC146"},
        }
        records = {
            code: {"source": "EDINET", "quality": {}}
            for code in filings
        }
        attempted = {"DOC130", "DOC146"}

        candidates = update_tdnet_financials_overlay_strict.select_candidates(
            filings,
            records,
            lookback_days=31,
            backfill_limit=1,
            max_documents=10,
            attempted_document_ids=attempted,
        )

        self.assertEqual([candidate["code"] for candidate in candidates], ["130A"])
        self.assertEqual(attempted, set())

    def test_priority_code_is_selected_before_normal_backfill_order(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        filings = {
            "130A": {"code": "130A", "filedAt": old, "documentId": "DOC130"},
            "146A": {"code": "146A", "filedAt": old, "documentId": "DOC146"},
        }
        records = {
            code: {"source": "EDINET", "quality": {}}
            for code in filings
        }

        candidates = update_tdnet_financials_overlay_strict.select_candidates(
            filings,
            records,
            lookback_days=31,
            backfill_limit=1,
            max_documents=10,
            priority_codes=["146A"],
        )

        self.assertEqual([candidate["code"] for candidate in candidates], ["146A"])

    def test_same_period_tdnet_roe_enriches_newer_edinet_record(self) -> None:
        existing = record("146A", "2025-12-31")
        existing["metrics"]["roe"] = {
            "value": 23.46,
            "previousValue": 23.26,
            "trend": [23.26, 23.46],
        }
        existing["history"] = [
            {"year": "2024/12", "roe": 23.26},
            {"year": "2025/12", "roe": 23.46},
        ]
        tdnet = {
            "periodEnd": "2025-12-31",
            "documentId": "TDNET1",
            "sourceUrl": "https://example.test/tdnet.pdf",
            "metrics": {
                "roe": {
                    "value": 23.5,
                    "previousValue": 23.2,
                    "trend": [23.2, 23.5],
                }
            },
            "history": [
                {"year": "2024/12", "roe": 23.2},
                {"year": "2025/12", "roe": 23.5},
            ],
        }

        changed = (
            update_tdnet_financials_overlay_strict.merge_same_period_disclosed_roe(
                existing,
                tdnet,
            )
        )

        self.assertTrue(changed)
        self.assertEqual(existing["metrics"]["roe"]["value"], 23.5)
        self.assertEqual(existing["metrics"]["roe"]["previousValue"], 23.2)
        self.assertEqual(
            [point["roe"] for point in existing["history"]],
            [23.2, 23.5],
        )
        self.assertEqual(existing["quality"]["roeDocumentId"], "TDNET1")


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

    def test_selected_fact_retains_audit_metadata(self) -> None:
        contexts = {
            "CurrentYearDuration": {
                "start": "2025-04-01",
                "end": "2026-03-31",
                "instant": None,
                "dimensions": [],
            }
        }
        facts = {
            "NetSales": [
                (
                    "CurrentYearDuration",
                    100.0,
                    {
                        "tag": "jppfs_cor:NetSales",
                        "unitRef": "JPY",
                        "scale": "0",
                    },
                )
            ]
        }

        selected = data_quality.select_preferred_facts(
            contexts,
            facts,
            ("NetSales",),
            True,
        )["2026-03-31"]

        self.assertEqual(selected["tag"], "jppfs_cor:NetSales")
        self.assertEqual(selected["contextRef"], "CurrentYearDuration")
        self.assertEqual(selected["unitRef"], "JPY")
        self.assertEqual(selected["scale"], "0")
        self.assertEqual(selected["consolidation"], "consolidated")
        self.assertEqual(selected["periodType"], "duration")
        self.assertEqual(selected["rawValue"], 100.0)

    def test_metric_provenance_references_current_and_previous_facts(self) -> None:
        selected = {
            "revenue": {
                "2025-03-31": [{"concept": "NetSales", "contextRef": "Prior"}],
                "2026-03-31": [{"concept": "NetSales", "contextRef": "Current"}],
            }
        }
        inputs = data_quality.provenance_inputs(
            selected,
            ("revenue",),
            "2026-03-31",
            include_previous=True,
        )
        metrics = {"revenueGrowth": {"value": 5.0}}
        data_quality.attach_metric_provenance(
            metrics,
            "revenueGrowth",
            "(revenue.current / revenue.previous - 1) * 100",
            inputs,
        )

        provenance = metrics["revenueGrowth"]["provenance"]
        self.assertEqual(
            [fact["role"] for fact in provenance["sourceFacts"]],
            ["revenue.current", "revenue.previous"],
        )
        self.assertIn("revenue.previous", provenance["formula"])


class BatchedMigrationTests(unittest.TestCase):
    def test_roe_history_mismatch_is_prioritized_for_refresh(self) -> None:
        stale = record("146A", "2025-12-31")
        stale["metrics"]["roe"] = {
            "value": 23.47,
            "previousValue": 18.5,
        }
        stale["history"] = [
            {"year": "2024/12", "roe": 23.26},
            {"year": "2025/12", "roe": 23.47},
        ]
        consistent = record("1000", "2025-12-31")
        consistent["metrics"]["roe"] = {
            "value": 12.0,
            "previousValue": 10.0,
        }
        consistent["history"] = [
            {"year": "2024/12", "roe": 10.0},
            {"year": "2025/12", "roe": 12.0},
        ]

        self.assertTrue(
            update_edinet_financials_batched.record_has_roe_history_mismatch(stale)
        )
        self.assertFalse(
            update_edinet_financials_batched.record_has_roe_history_mismatch(consistent)
        )

    def test_v5_fractional_roe_is_prioritized_for_scale_refresh(self) -> None:
        stale = record("146A", "2025-12-31")
        stale["metrics"]["roe"] = {
            "value": 0.23,
            "previousValue": 0.23,
        }
        stale["history"] = [
            {"year": "2024/12", "roe": 0.23},
            {"year": "2025/12", "roe": 0.23},
        ]
        stale["quality"] = {
            "dataModelVersion": update_edinet_financials_batched.DATA_MODEL_VERSION - 1
        }

        self.assertEqual(
            update_edinet_financials_batched.record_roe_refresh_priority(stale),
            3,
        )

    def test_candidate_priority_uses_preserved_alphanumeric_code(self) -> None:
        stale = record("146A", "2025-12-31")
        stale["metrics"]["roe"] = {"value": 0.23}
        stale["quality"] = {"dataModelVersion": 5}
        filing = {
            "secCode": None,
            "_normalizedCode": "146A",
            "periodEnd": "2025-12-31",
        }

        self.assertEqual(
            update_edinet_financials_batched.candidate_priority_key(
                filing, {"146A": stale}
            ),
            (-3, "146A"),
        )

    def test_priority_recovery_uses_small_canary_batch(self) -> None:
        self.assertEqual(
            update_edinet_financials_batched.refresh_batch_size(700, True, True),
            50,
        )
        self.assertEqual(
            update_edinet_financials_batched.refresh_batch_size(700, False, True),
            50,
        )
        self.assertEqual(
            update_edinet_financials_batched.refresh_batch_size(700, True, False),
            700,
        )

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
