from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_edinet_financials
import update_edinet_financials_batched


def xbrl_instance(concept: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:jppfs_cor="http://example.test/jppfs">
  <jppfs_cor:{concept} contextRef="CurrentYearDuration" unitRef="JPY">100</jppfs_cor:{concept}>
</xbrli:xbrl>
""".encode("utf-8")


class EdinetInstanceSelectionTests(unittest.TestCase):
    def test_primary_financial_instance_beats_shorter_decoy(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "XBRL/PublicDoc/a.xbrl",
                xbrl_instance("UnrelatedCompanyExtensionFact"),
            )
            archive.writestr(
                "XBRL/PublicDoc/jpcrp030000-asr-001.xbrl",
                xbrl_instance("RevenueIFRS"),
            )

        selected = update_edinet_financials.xbrl_from_zip(buffer.getvalue())

        self.assertIn(b"RevenueIFRS", selected)
        self.assertNotIn(b"UnrelatedCompanyExtensionFact", selected)

    def test_financial_fact_count_ignores_unrelated_extension_facts(self) -> None:
        self.assertEqual(
            update_edinet_financials.financial_fact_count(
                xbrl_instance("UnrelatedCompanyExtensionFact")
            ),
            0,
        )
        self.assertEqual(
            update_edinet_financials.financial_fact_count(
                xbrl_instance("ProfitLossAttributableToOwnersOfParentIFRS")
            ),
            1,
        )


class MissingGoldenPriorityTests(unittest.TestCase):
    def test_missing_golden_company_precedes_normal_candidate(self) -> None:
        records: dict[str, dict] = {}
        normal = {"_normalizedCode": "1000"}
        golden = {"_normalizedCode": "6301"}

        ordered = sorted(
            [normal, golden],
            key=lambda filing: update_edinet_financials_batched.candidate_priority_key(
                filing,
                records,
                {"6301"},
            ),
        )

        self.assertEqual(
            [candidate["_normalizedCode"] for candidate in ordered],
            ["6301", "1000"],
        )

    def test_existing_golden_record_is_not_forced_to_front(self) -> None:
        records = {"6301": {"source": "EDINET", "quality": {"dataModelVersion": 9}}}
        priority = update_edinet_financials_batched.candidate_priority_key(
            {"_normalizedCode": "6301"},
            records,
            {"6301"},
        )

        self.assertEqual(priority, (0, ""))


class EdinetSummaryFactTests(unittest.TestCase):
    def test_summary_tags_are_available_for_annual_fallback(self) -> None:
        self.assertIn(
            "NetSalesSummaryOfBusinessResults",
            update_edinet_financials.FACT_NAMES["revenue"],
        )
        self.assertIn(
            "ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
            update_edinet_financials.FACT_NAMES["profit"],
        )
        self.assertIn(
            "TotalAssetsSummaryOfBusinessResults",
            update_edinet_financials.FACT_NAMES["assets"],
        )

    def test_us_gaap_tags_are_available_for_financial_issuers(self) -> None:
        self.assertIn(
            "RevenuesUSGAAP",
            update_edinet_financials.FACT_NAMES["revenue"],
        )
        self.assertIn(
            "NetIncomeLossAttributableToOwnersOfParentUSGAAP",
            update_edinet_financials.FACT_NAMES["profit"],
        )
        self.assertIn(
            "AssetsUSGAAP",
            update_edinet_financials.FACT_NAMES["assets"],
        )


class EmptyRecordDiagnosticTests(unittest.TestCase):
    def test_diagnostics_expose_visible_financial_concepts(self) -> None:
        diagnostic = update_edinet_financials.empty_record_diagnostics(
            xbrl_instance("RevenueIFRS"),
            "2026-03-31",
        )

        self.assertIn("numericFacts=1", diagnostic)
        self.assertIn("RevenueIFRS", diagnostic)

    def test_priority_recovery_batch_is_bounded(self) -> None:
        self.assertEqual(
            update_edinet_financials_batched.refresh_batch_size(
                350,
                data_model_upgraded=False,
                has_priority_candidates=True,
            ),
            50,
        )


if __name__ == "__main__":
    unittest.main()
