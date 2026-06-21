from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "src" / "lib" / "industryKpiPolicy.ts"
GOLDEN_PATH = ROOT / "src" / "lib" / "goldenIndustryCases.ts"

CASE_PATTERN = re.compile(
    r"\{\s*\n"
    r"\s*code: '([^']+)',\s*\n"
    r"\s*companyName: '([^']+)',\s*\n"
    r"\s*industry: '([^']+)',\s*\n"
    r".*?"
    r"\s*riskFlags: (\[[^\]]*\]),\s*\n"
    r"\s*minimumKpis:",
    re.DOTALL,
)


def _extract_string_array(source: str, name: str) -> list[str]:
    match = re.search(rf"export const {name} = \[(.*?)\] as const", source, re.DOTALL)
    if not match:
        raise AssertionError(f"Could not find exported array {name}")
    return re.findall(r"'([^']+)'", match.group(1))


def _extract_golden_cases() -> list[dict[str, object]]:
    source = GOLDEN_PATH.read_text(encoding="utf-8")
    cases = []
    for code, company_name, industry, risk_flags_source in CASE_PATTERN.findall(source):
        cases.append(
            {
                "code": code,
                "companyName": company_name,
                "industry": industry,
                "riskFlags": ast.literal_eval(risk_flags_source),
            }
        )
    return cases


class GoldenIndustryCaseManifestTests(unittest.TestCase):
    def test_manifest_contains_40_to_50_unique_real_company_cases(self) -> None:
        cases = _extract_golden_cases()
        codes = [case["code"] for case in cases]

        self.assertGreaterEqual(len(cases), 40)
        self.assertLessEqual(len(cases), 50)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(re.fullmatch(r"\d{4}|\d{3}[A-Z]", code) for code in codes))

    def test_manifest_covers_all_33_jpx_industries(self) -> None:
        policy_source = POLICY_PATH.read_text(encoding="utf-8")
        expected_industries = set(_extract_string_array(policy_source, "jpxIndustries"))
        actual_industries = {str(case["industry"]) for case in _extract_golden_cases()}

        self.assertEqual(len(expected_industries), 33)
        self.assertEqual(actual_industries, expected_industries)

    def test_manifest_preserves_high_risk_regression_cases(self) -> None:
        cases = _extract_golden_cases()
        risk_codes: dict[str, set[str]] = {}
        for case in cases:
            for flag in case["riskFlags"]:  # type: ignore[union-attr]
                risk_codes.setdefault(str(flag), set()).add(str(case["code"]))

        required_flags = {
            "bank-policy",
            "securities-policy",
            "insurance-policy",
            "other-financial-policy",
            "real-estate-inventory",
            "stale-roe-scale",
            "low-roe-not-zero",
            "loss-making",
            "large-cap-cross-check",
            "capital-intensive",
        }
        self.assertTrue(required_flags.issubset(risk_codes))
        self.assertTrue({"5987", "5988", "7083", "8217"}.issubset(risk_codes["stale-roe-scale"]))
        self.assertIn("146A", risk_codes["real-estate-inventory"])

    def test_financial_industry_policies_remain_restricted(self) -> None:
        policy_source = POLICY_PATH.read_text(encoding="utf-8")

        self.assertIn("const bankPolicy = createPolicy(\n  ['roe', 'per', 'pbr']", policy_source)
        self.assertIn("const securitiesPolicy = createPolicy(\n  ['roe', 'per', 'pbr']", policy_source)
        self.assertIn("const insurancePolicy = createPolicy(\n  ['roe', 'per', 'pbr']", policy_source)
        self.assertIn(
            "const otherFinancialPolicy = createPolicy(\n  ['revenueGrowth', 'netMargin', 'roe', 'per', 'pbr']",
            policy_source,
        )


if __name__ == "__main__":
    unittest.main()
