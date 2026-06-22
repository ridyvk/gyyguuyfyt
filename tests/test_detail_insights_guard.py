from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIVE_DATA = ROOT / "src" / "lib" / "liveData.ts"
DETAIL_INSIGHTS = ROOT / "src" / "lib" / "detailInsights.ts"
COMPANY_DETAIL = ROOT / "src" / "pages" / "CompanyDetail.tsx"
ANALYSIS = ROOT / "src" / "lib" / "analysis.ts"


class DetailInsightsGuardTests(unittest.TestCase):
    def test_live_records_generate_industry_insights_and_analysis_levels(self) -> None:
        source = LIVE_DATA.read_text(encoding="utf-8")
        self.assertIn("industryKpis: buildIndustryInsights(metrics, applicable)", source)
        self.assertIn("const analysisLevel = getAnalysisLevel(", source)
        self.assertIn("analysisComment: buildTieredAnalysisComment(", source)
        self.assertIn("trustedMetricCount: scoringAvailable.size", source)
        self.assertIn("export const hasScorableData", source)

    def test_reference_values_stay_visible_but_are_labeled(self) -> None:
        source = DETAIL_INSIGHTS.read_text(encoding="utf-8")
        self.assertIn("metric.confidence === 'C' || metric.confidence === 'review'", source)
        self.assertIn("スコア対象となる信頼度A/BのKPIはまだありません", source)
        self.assertIn("buildIndustryInsights", source)

        detail = COMPANY_DETAIL.read_text(encoding="utf-8")
        self.assertIn("参考分析", detail)
        self.assertIn("industry-kpi-confidence", detail)
        self.assertIn("indeterminate={analysisLevel === 'reference'}", detail)

    def test_strengths_do_not_claim_stability_without_evidence(self) -> None:
        source = ANALYSIS.read_text(encoding="utf-8")
        self.assertNotIn("業績は概ね安定圏で推移", source)
        self.assertIn("return strengths.slice(0, 4)", source)


if __name__ == "__main__":
    unittest.main()
