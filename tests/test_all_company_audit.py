from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_all_companies


def company(code: str, industry: str = "サービス業") -> dict:
    return {
        "code": code,
        "name": f"Company {code}",
        "market": "プライム",
        "industry": industry,
    }


def record(code: str) -> dict:
    return {
        "code": code,
        "companyName": f"Company {code}",
        "documentId": f"DOC-{code}",
        "periodEnd": "2026-03-31",
        "source": "EDINET",
        "sourceUrl": f"https://example.test/{code}",
        "metrics": {
            "roe": {
                "value": 10.0,
                "provenance": {
                    "formula": "disclosedRoe * 100",
                    "sourceFacts": [
                        {
                            "tag": "RateOfReturnOnEquitySummaryOfBusinessResults",
                            "contextRef": "CurrentYearDuration",
                            "unitRef": "pure",
                            "consolidation": "consolidated",
                        }
                    ],
                },
            }
        },
        "quality": {
            "dataModelVersion": 9,
            "provenanceModelVersion": 1,
        },
    }


class AllCompanyAuditTests(unittest.TestCase):
    def test_report_classifies_ok_warning_review_and_missing(self) -> None:
        master = {
            "companyCount": 4,
            "companies": [
                company("1000"),
                company("1001"),
                company("1002"),
                company("1003"),
            ],
        }
        warning = record("1001")
        warning["metrics"]["roe"].pop("provenance")
        review = record("1002")
        review["quarantine"] = {
            "metricValidation": {
                "metrics": {"equityRatio": {"reason": "above-maximum-100"}}
            }
        }
        snapshot = {
            "generatedAt": "2026-06-21T00:00:00Z",
            "records": {
                "1000": record("1000"),
                "1001": warning,
                "1002": review,
            },
        }

        report = audit_all_companies.build_report(
            master,
            snapshot,
            today=date(2026, 6, 21),
        )

        self.assertEqual(
            report["summary"],
            {
                "companies": 4,
                "recordsAvailable": 3,
                "coverageRatio": 75.0,
                "ok": 1,
                "warning": 1,
                "review": 1,
                "missing": 1,
                "issueCounts": {
                    "metric-range-quarantined": 1,
                    "missing-financial-record": 1,
                    "missing-provenance": 1,
                },
                "sourceCounts": {
                    "EDINET": 3,
                    "unavailable": 1,
                },
            },
        )
        statuses = {
            item["code"]: item["status"]
            for item in report["companies"]
        }
        self.assertEqual(
            statuses,
            {
                "1000": "ok",
                "1001": "warning",
                "1002": "review",
                "1003": "missing",
            },
        )
        self.assertEqual(report["violations"], [])

    def test_incomplete_source_fact_fields_are_reported(self) -> None:
        broken = record("1000")
        del broken["metrics"]["roe"]["provenance"]["sourceFacts"][0]["unitRef"]

        result = audit_all_companies.audit_company(
            company("1000"),
            broken,
            date(2026, 6, 21),
        )

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["provenanceMetricCount"], 0)
        self.assertEqual(
            {issue["code"] for issue in result["issues"]},
            {"missing-provenance", "incomplete-provenance-facts"},
        )

    def test_previous_report_establishes_non_regression_baseline(self) -> None:
        summary = {
            "missing": 11,
            "review": 4,
            "recordsAvailable": 89,
        }
        previous = {
            "schemaVersion": audit_all_companies.SCHEMA_VERSION,
            "summary": {
                "missing": 10,
                "review": 3,
                "recordsAvailable": 90,
            },
        }

        violations = audit_all_companies.regression_violations(summary, previous)

        self.assertEqual(
            {violation["field"] for violation in violations},
            {"missing", "review", "recordsAvailable"},
        )

    def test_schema_change_resets_regression_baseline(self) -> None:
        violations = audit_all_companies.regression_violations(
            {"missing": 100, "review": 50, "recordsAvailable": 1},
            {
                "schemaVersion": 0,
                "summary": {
                    "missing": 0,
                    "review": 0,
                    "recordsAvailable": 100,
                },
            },
        )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
