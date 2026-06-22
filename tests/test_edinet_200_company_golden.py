from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "edinet_200_company_golden.json"
FINANCIALS = ROOT / "public" / "data" / "financials.json"
COMPANY_MASTER = ROOT / "src" / "data" / "listedCompanies.json"

FACT_FIELDS = (
    "role",
    "tag",
    "contextRef",
    "periodStart",
    "periodEnd",
    "periodType",
    "unitRef",
    "consolidation",
    "dimensions",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fact_signature(fact: dict) -> dict:
    return {
        key: fact[key]
        for key in FACT_FIELDS
        if key in fact and fact[key] is not None and fact[key] != []
    }


class Edinet200CompanyGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_json(FIXTURE)
        cls.snapshot = load_json(FINANCIALS)
        cls.master = load_json(COMPANY_MASTER)
        cls.master_by_code = {
            str(company["code"]): company
            for company in cls.master.get("companies", [])
        }

    def test_cohort_is_fixed_at_200_unique_companies_across_33_industries(self) -> None:
        companies = self.fixture["companies"]
        codes = [company["code"] for company in companies]
        industries = Counter(company["industry"] for company in companies)

        self.assertEqual(self.fixture["schemaVersion"], 1)
        self.assertEqual(len(companies), 200)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(len(industries), 33)
        self.assertTrue(all(count >= 1 for count in industries.values()))

    def test_only_air_transport_is_a_legacy_provenance_exception(self) -> None:
        companies = self.fixture["companies"]
        legacy = [
            company for company in companies if company.get("legacyProvenance")
        ]

        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]["code"], "9201")
        self.assertEqual(legacy[0]["industry"], "空運業")
        self.assertEqual(self.fixture["summary"]["strictProvenance"], 199)
        self.assertEqual(self.fixture["summary"]["legacyProvenance"], 1)

    def test_strict_cases_pin_real_xbrl_source_fields(self) -> None:
        required = {
            "role",
            "tag",
            "contextRef",
            "periodEnd",
            "periodType",
            "unitRef",
            "consolidation",
        }
        for company in self.fixture["companies"]:
            if company.get("legacyProvenance"):
                continue
            self.assertEqual(company["source"], "EDINET", company["code"])
            self.assertTrue(company["documentId"], company["code"])
            self.assertTrue(company["anchors"], company["code"])
            for metric_key, anchor in company["anchors"].items():
                self.assertTrue(anchor.get("formula"), (company["code"], metric_key))
                self.assertTrue(anchor.get("sourceFacts"), (company["code"], metric_key))
                for fact in anchor["sourceFacts"]:
                    self.assertTrue(
                        required.issubset(fact),
                        (company["code"], metric_key, fact),
                    )
                    self.assertIn(
                        fact["consolidation"],
                        {"consolidated", "unknown"},
                    )

    def test_live_snapshot_matches_golden_for_unchanged_documents(self) -> None:
        records = self.snapshot.get("records", {})
        same_document = 0
        refreshed_documents = []

        for company in self.fixture["companies"]:
            code = company["code"]
            record = records.get(code)
            self.assertIsInstance(record, dict, code)
            self.assertEqual(
                self.master_by_code[code]["industry"],
                company["industry"],
                code,
            )
            if record.get("documentId") != company["documentId"]:
                self.assertGreaterEqual(
                    str(record.get("periodEnd") or ""),
                    company["periodEnd"],
                    code,
                )
                refreshed_documents.append(code)
                continue

            same_document += 1
            self.assertEqual(record.get("periodEnd"), company["periodEnd"], code)
            for metric_key, expected in company["anchors"].items():
                actual = (record.get("metrics") or {}).get(metric_key)
                self.assertIsInstance(actual, dict, (code, metric_key))
                if metric_key == "roe":
                    self.assertAlmostEqual(
                        actual.get("value"),
                        expected["value"],
                        delta=0.1,
                        msg=(code, metric_key),
                    )
                else:
                    self.assertEqual(
                        actual.get("value"),
                        expected["value"],
                        (code, metric_key),
                    )
                if "previousValue" in expected:
                    self.assertEqual(
                        actual.get("previousValue"),
                        expected["previousValue"],
                        (code, metric_key),
                    )
                if company.get("legacyProvenance"):
                    continue
                provenance = actual.get("provenance") or {}
                self.assertEqual(
                    provenance.get("formula"),
                    expected["formula"],
                    (code, metric_key),
                )
                self.assertEqual(
                    [fact_signature(fact) for fact in provenance.get("sourceFacts", [])],
                    expected["sourceFacts"],
                    (code, metric_key),
                )

        self.assertGreaterEqual(same_document, 180)
        self.assertLessEqual(len(refreshed_documents), 20)


if __name__ == "__main__":
    unittest.main()
