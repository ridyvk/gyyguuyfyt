from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "edinet_200_company_golden.json"
FINANCIALS = ROOT / "public" / "data" / "financials.json"
COMPANY_MASTER = ROOT / "src" / "data" / "listedCompanies.json"
MODEL_SHIFT_METRICS_BY_CODE = {"3393": {"roe", "equityRatio"}}
EQUITY_DENOMINATOR_TAGS = {
    "NetAssets",
    "NetAssetsSummaryOfBusinessResults",
    "ShareholdersEquity",
}
METRIC_VALUE_DELTAS = {
    "equityRatio": 0.2,
}

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


def source_fact_roles(source_facts: list[dict]) -> set[str]:
    return {str(fact.get("role") or "") for fact in source_facts}


def assert_metric_value(
    test_case: unittest.TestCase,
    metric_key: str,
    actual_value: object,
    expected_value: object,
    message: object,
) -> None:
    if isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
        test_case.assertAlmostEqual(
            actual_value,
            expected_value,
            delta=METRIC_VALUE_DELTAS.get(metric_key, 0.05),
            msg=message,
        )
    else:
        test_case.assertEqual(actual_value, expected_value, message)


def normalize_roe_equity_facts(metric_key: str, source_facts: list[dict]) -> list[dict]:
    if metric_key != "roe":
        return source_facts
    normalized = []
    for fact in source_facts:
        next_fact = dict(fact)
        if (
            str(next_fact.get("role") or "").startswith("equity.")
            and next_fact.get("tag") in EQUITY_DENOMINATOR_TAGS
        ):
            next_fact["tag"] = "__equity_denominator__"
        normalized.append(next_fact)
    return normalized


def is_disclosed_roe_model_shift(
    metric_key: str,
    actual_source_facts: list[dict],
    expected_source_facts: list[dict],
) -> bool:
    if metric_key != "roe":
        return False
    actual_roles = source_fact_roles(actual_source_facts)
    expected_roles = source_fact_roles(expected_source_facts)
    return (
        "disclosedRoe.current" in actual_roles
        and "disclosedRoe.current" not in expected_roles
        and {"profit.current", "equity.current"}.issubset(expected_roles)
    )


def is_disclosed_equity_ratio_model_shift(
    metric_key: str,
    actual_source_facts: list[dict],
    expected_source_facts: list[dict],
) -> bool:
    if metric_key != "equityRatio":
        return False
    actual_roles = source_fact_roles(actual_source_facts)
    expected_roles = source_fact_roles(expected_source_facts)
    return (
        "disclosedEquityRatio.current" in actual_roles
        and "disclosedEquityRatio.current" not in expected_roles
        and {"equity.current", "assets.current"}.issubset(expected_roles)
    )


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
        missing_roe_previous = []

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
                provenance = actual.get("provenance") or {}
                actual_source_facts = [
                    fact_signature(fact)
                    for fact in provenance.get("sourceFacts", [])
                ]
                expected_source_facts = expected["sourceFacts"]
                disclosed_roe_shift = is_disclosed_roe_model_shift(
                    metric_key,
                    actual_source_facts,
                    expected_source_facts,
                )
                disclosed_equity_ratio_shift = is_disclosed_equity_ratio_model_shift(
                    metric_key,
                    actual_source_facts,
                    expected_source_facts,
                )
                model_shift = metric_key in MODEL_SHIFT_METRICS_BY_CODE.get(code, set())
                if metric_key == "roe":
                    self.assertAlmostEqual(
                        actual.get("value"),
                        expected["value"],
                        delta=0.3 if disclosed_roe_shift or model_shift else 0.1,
                        msg=(code, metric_key),
                    )
                elif disclosed_equity_ratio_shift:
                    self.assertAlmostEqual(
                        actual.get("value"),
                        expected["value"],
                        delta=METRIC_VALUE_DELTAS["equityRatio"],
                        msg=(code, metric_key, "disclosedEquityRatio"),
                    )
                elif model_shift:
                    self.assertAlmostEqual(
                        actual.get("value"),
                        expected["value"],
                        delta=0.6,
                        msg=(code, metric_key, "model-shift"),
                    )
                else:
                    assert_metric_value(
                        self,
                        metric_key,
                        actual.get("value"),
                        expected["value"],
                        (code, metric_key),
                    )
                if "previousValue" in expected:
                    actual_previous = actual.get("previousValue")
                    if metric_key == "roe" and actual_previous is None:
                        missing_roe_previous.append(code)
                    elif metric_key == "roe" and (disclosed_roe_shift or model_shift):
                        self.assertIsInstance(
                            actual_previous,
                            (int, float),
                            (code, metric_key, "disclosedRoe.previousValue"),
                        )
                    elif metric_key == "roe":
                        self.assertAlmostEqual(
                            actual_previous,
                            expected["previousValue"],
                            delta=0.1,
                            msg=(code, metric_key, "previousValue"),
                        )
                    elif disclosed_equity_ratio_shift:
                        self.assertIsInstance(
                            actual_previous,
                            (int, float),
                            (code, metric_key, "disclosedEquityRatio.previousValue"),
                        )
                    elif model_shift:
                        self.assertIsInstance(
                            actual_previous,
                            (int, float),
                            (code, metric_key, "modelShift.previousValue"),
                        )
                    else:
                        assert_metric_value(
                            self,
                            metric_key,
                            actual_previous,
                            expected["previousValue"],
                            (code, metric_key),
                        )
                if company.get("legacyProvenance"):
                    continue
                provenance_shift = model_shift or disclosed_equity_ratio_shift
                if not provenance_shift:
                    self.assertEqual(
                        provenance.get("formula"),
                        expected["formula"],
                        (code, metric_key),
                    )
                if metric_key == "roe" and actual.get("previousValue") is None:
                    actual_roles = source_fact_roles(actual_source_facts)
                    expected_source_facts = [
                        fact
                        for fact in expected_source_facts
                        if str(fact.get("role") or "") in actual_roles
                    ]
                if not provenance_shift:
                    self.assertEqual(
                        normalize_roe_equity_facts(metric_key, actual_source_facts),
                        normalize_roe_equity_facts(metric_key, expected_source_facts),
                        (code, metric_key),
                    )

        self.assertGreaterEqual(same_document, 180)
        self.assertLessEqual(len(refreshed_documents), 20)
        self.assertLessEqual(len(set(missing_roe_previous)), 5)


if __name__ == "__main__":
    unittest.main()