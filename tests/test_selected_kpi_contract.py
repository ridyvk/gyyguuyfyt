from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]

SELECTED_KPIS = [
    "revenueGrowth",
    "operatingMargin",
    "netMargin",
    "roe",
    "equityRatio",
    "operatingCfMargin",
    "debtRatio",
    "netCash",
    "inventoryGrowth",
    "receivablesGrowth",
    "per",
    "pbr",
]

REMOVED_KPIS = [
    "operatingIncomeGrowth",
    "epsGrowth",
    "roa",
    "roic",
    "roicWaccSpread",
    "cashProfitGap",
    "wacc",
    "ebitda",
    "evEbitda",
]


class SelectedKpiContractTests(unittest.TestCase):
    def test_kpi_type_contains_only_the_selected_metrics(self):
        source = (ROOT / "src" / "types.ts").read_text(encoding="utf-8")
        match = re.search(
            r"export type KpiKey =(?P<body>.*?)export interface KpiMetric",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        actual = re.findall(r"'([^']+)'", match.group("body"))
        self.assertEqual(actual, SELECTED_KPIS)

    def test_removed_metrics_are_not_used_by_the_app(self):
        source_files = [
            *ROOT.glob("src/**/*.ts"),
            *ROOT.glob("src/**/*.tsx"),
        ]
        app_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in source_files
            if "src/data" not in path.as_posix()
        )
        for metric in REMOVED_KPIS:
            with self.subTest(metric=metric):
                self.assertIsNone(
                    re.search(rf"\b{re.escape(metric)}\b", app_source, re.IGNORECASE)
                )


if __name__ == "__main__":
    unittest.main()
