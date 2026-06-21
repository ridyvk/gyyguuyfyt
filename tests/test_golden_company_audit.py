from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_golden_companies


def case(**overrides: object) -> dict:
    value = {
        "code": "1234",
        "companyName": "テスト会社",
        "industry": "機械",
        "riskFlags": [],
    }
    value.update(overrides)
    return value


def record(**overrides: object) -> dict:
    value = {
        "code": "1234",
        "source": "EDINET",
        "periodEnd": "2026-03-31",
        "metrics": {
            "roe": {
                "value": 5.0,
                "provenance": {"sourceFacts": [{"tag": "ReturnOnEquity"}]},
            }
        },
        "quality": {
            "dataModelVersion": 9,
            "provenanceModelVersion": 1,
        },
    }
    value.update(overrides)
    return value


class GoldenCompanyAuditTests(unittest.TestCase):
    def test_current_record_is_healthy(self) -> None:
        result = audit_golden_companies.audit_case(
            case(),
            record(),
            {"code": "1234", "industry": "機械"},
            date(2026, 6, 21),
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["issues"], [])

    def test_low_roe_case_cannot_regress_to_zero(self) -> None:
        result = audit_golden_companies.audit_case(
            case(riskFlags=["low-roe-not-zero"]),
            record(
                metrics={
                    "roe": {
                        "value": 0.0,
                        "provenance": {"sourceFacts": [{"tag": "ReturnOnEquity"}]},
                    }
                }
            ),
            {"code": "1234", "industry": "機械"},
            date(2026, 6, 21),
        )
        issue_codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("low-roe-regressed-to-zero", issue_codes)
        self.assertEqual(result["status"], "critical")

    def test_missing_record_is_reported_without_hiding_the_company(self) -> None:
        result = audit_golden_companies.audit_case(
            case(),
            None,
            {"code": "1234", "industry": "機械"},
            date(2026, 6, 21),
        )
        self.assertEqual(result["code"], "1234")
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["issues"][0]["code"], "missing-record")

    def test_non_regression_budget_fails_when_missing_coverage_worsens(self) -> None:
        cases = [
            case(code=f"{index:04d}")
            for index in range(audit_golden_companies.MAX_MISSING_RECORDS + 1)
        ]
        master = {
            "companies": [
                {"code": item["code"], "industry": "機械"}
                for item in cases
            ]
        }
        report = audit_golden_companies.build_report(
            cases,
            {"generatedAt": "2026-06-21T00:00:00Z", "records": {}},
            master,
            date(2026, 6, 21),
        )
        fields = {violation["field"] for violation in report["violations"]}
        self.assertIn("missingRecords", fields)


if __name__ == "__main__":
    unittest.main()
