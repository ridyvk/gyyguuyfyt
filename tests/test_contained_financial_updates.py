from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_all_companies as audit
import audit_golden_companies as golden
import finalize_annual_dataset as finalize
import reconcile_financial_sources as reconcile


def sources():
    edinet = {
        "code": "1234", "documentId": "E1", "source": "EDINET",
        "periodEnd": "2026-03-31", "sourceUrl": "https://example.test/edinet",
        "quality": {"dataModelVersion": 9},
        "metrics": {"roe": {"value": 10}, "netMargin": {"value": 5}},
        "history": [{"year": "2026/03", "roe": 10, "roa": 4}],
    }
    tdnet = {
        **deepcopy(edinet), "source": "TDnet", "documentId": "T1",
        "sourceUrl": "https://example.test/tdnet",
        "metrics": {"roe": {"value": 20}, "netMargin": {"value": 5}},
    }
    return edinet, tdnet


def disputed_record():
    edinet, tdnet = sources()
    reconcile.reconcile_same_period(edinet, tdnet)
    return edinet


class ContainedFinancialUpdatesTests(unittest.TestCase):
    def test_repeated_filing_cannot_resurrect_disputed_value(self):
        edinet, tdnet = sources()
        for _ in range(3):
            reconcile.reconcile_same_period(edinet, tdnet)
            self.assertNotIn("roe", edinet["metrics"])
            self.assertNotIn("roe", edinet["history"][0])
            self.assertNotIn("roa", edinet["history"][0])
            self.assertEqual(reconcile.contained_source_quarantines(edinet), {"roe"})
            self.assertEqual(edinet["metrics"]["netMargin"]["value"], 5)

    def test_new_matching_filing_resolves_dispute(self):
        edinet, tdnet = sources()
        reconcile.reconcile_same_period(edinet, tdnet)
        tdnet["documentId"] = "T2"
        tdnet["metrics"]["roe"]["value"] = 10.1
        reconcile.reconcile_same_period(edinet, tdnet)
        self.assertEqual(edinet["metrics"]["roe"]["value"], 10.1)
        self.assertFalse(reconcile.disputed_metrics(edinet))
        self.assertEqual(edinet["reconciliation"]["status"], "matched")

    def test_partial_followup_keeps_original_dispute_evidence(self):
        edinet, tdnet = sources()
        reconcile.reconcile_same_period(edinet, tdnet)
        tdnet["documentId"] = "T2"
        del tdnet["metrics"]["roe"]
        reconcile.reconcile_same_period(edinet, tdnet)
        self.assertNotIn("roe", edinet["metrics"])
        self.assertEqual(reconcile.disputed_metrics(edinet)["roe"]["sources"]["TDnet"]["documentId"], "T1")
        self.assertEqual(reconcile.contained_source_quarantines(edinet), {"roe"})

    def test_golden_anchor_does_not_restore_disputed_metric(self):
        record = disputed_record()
        anchor = {"documentId": "E1", "periodEnd": "2026-03-31", "anchors": {"roe": {"value": 10}}}
        with patch.object(finalize, "load_golden_anchors", return_value={"1234": anchor}):
            finalize.apply_golden_anchors({"1234": record})
        self.assertNotIn("roe", record["metrics"])

    def test_leaked_values_and_missing_evidence_are_not_contained(self):
        for field in ("metric", "history", "derived", "evidence"):
            record = disputed_record()
            if field == "metric": record["metrics"]["roe"] = {"value": 10}
            if field == "history": record["history"][0]["roe"] = 10
            if field == "derived": record["metrics"]["roa"] = {"value": 4}
            if field == "evidence": reconcile.disputed_metrics(record)["roe"]["comparison"] = {}
            self.assertEqual(reconcile.contained_source_quarantines(record), set(), field)

    def test_bounded_contained_disputes_are_partial_without_blocking_updates(self):
        previous = {"schemaVersion": audit.SCHEMA_VERSION, "summary": {"review": 2, "sourceQuarantinedMetrics": 0}}
        summary = {"review": 3, "sourceQuarantinedMetrics": 1, "containedSourceQuarantinedMetrics": 1, "containedSourceReviewCompanies": 1, "containedSourceCompanyRate": 0.1}
        self.assertEqual(audit.regression_violations(summary, previous), [])
        self.assertEqual(summary["review"], 3)
        self.assertEqual(summary["sourceQuarantinedMetrics"], 1)

    def test_uncontained_dispute_blocks_even_without_baseline(self):
        violations = audit.regression_violations({"sourceQuarantinedMetrics": 1}, {})
        self.assertEqual([v["field"] for v in violations], ["sourceQuarantinedMetrics"])

    def test_widespread_contained_disputes_still_block(self):
        violations = audit.regression_violations({"containedSourceCompanyRate": 1.1}, {})
        self.assertEqual([v["field"] for v in violations], ["containedSourceCompanyRate"])

    def test_golden_low_roe_check_is_scoped_to_original_fiscal_period(self):
        case = {"code": "1234", "industry": "機械", "riskFlags": ["low-roe-not-zero"], "roeRegressionPeriodEnd": "2025-03-31"}
        record, _ = sources()
        record["metrics"]["roe"]["value"] = 0
        master = {"code": "1234", "industry": "機械"}
        result = golden.audit_case(case, record, master, date(2026, 9, 9))
        self.assertNotEqual(result["status"], "critical")
        record["periodEnd"] = "2025-03-31"
        result = golden.audit_case(case, record, master, date(2026, 9, 9))
        self.assertEqual(result["status"], "critical")

    def test_contained_missing_roe_is_not_a_fabricated_zero(self):
        case = {"code": "1234", "industry": "機械", "riskFlags": ["low-roe-not-zero"]}
        result = golden.audit_case(case, disputed_record(), {"code": "1234", "industry": "機械"}, date(2026, 9, 9))
        self.assertNotEqual(result["status"], "critical")
        self.assertIn("roe-source-dispute", {i["code"] for i in result["issues"]})

    def test_unavailable_roe_in_new_period_remains_a_visible_warning(self):
        case = {"code": "1234", "industry": "機械", "riskFlags": ["low-roe-not-zero"], "roeRegressionPeriodEnd": "2025-03-31"}
        record, _ = sources()
        del record["metrics"]["roe"]
        result = golden.audit_case(case, record, {"code": "1234", "industry": "機械"}, date(2026, 9, 9))
        self.assertEqual(result["status"], "warning")
        self.assertIn("roe-unavailable-current-period", {i["code"] for i in result["issues"]})

    def test_audit_recounts_disputes_and_detects_exposure_from_records(self):
        master = {"companies": [{"code": "1234", "name": "Example", "industry": "機械"}]}
        record = disputed_record()
        snapshot = {"records": {"1234": record}, "stats": {"sourceQuarantinedMetrics": 0}}
        report = audit.build_report(master, snapshot, today=date(2026, 9, 9))
        self.assertEqual(report["summary"]["sourceQuarantinedMetrics"], 1)
        self.assertEqual(report["summary"]["containedSourceQuarantinedMetrics"], 1)
        record["metrics"]["roe"] = {"value": 10}
        report = audit.build_report(master, snapshot, today=date(2026, 9, 9))
        self.assertEqual(report["summary"]["containedSourceQuarantinedMetrics"], 0)
        self.assertIn("sourceQuarantinedMetrics", {v["field"] for v in report["violations"]})


if __name__ == "__main__":
    unittest.main()
