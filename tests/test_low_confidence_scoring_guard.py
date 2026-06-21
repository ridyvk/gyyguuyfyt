from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIVE_DATA = ROOT / 'src' / 'lib' / 'liveData.ts'

class LowConfidenceScoringGuardTests(unittest.TestCase):
    def test_scoring_uses_confidence_filtered_available_set(self) -> None:
        source = LIVE_DATA.read_text(encoding='utf-8')
        self.assertIn("const isScoreEligibleAssessment", source)
        self.assertIn("assessment.confidence === 'A' || assessment.confidence === 'B'", source)
        self.assertIn("const scoringAvailable = new Set<KpiKey>", source)
        self.assertIn("scores: calculateLiveScores(rawMetrics, scoringAvailable)", source)
        self.assertIn("strengths: buildStrengths(rawMetrics, scoringAvailable)", source)
        self.assertIn("buildAnalysisComment(\n      rawMetrics,\n      warnings,\n      previousOperatingMargin,\n      scoringAvailable", source)
        self.assertIn("liveMetricCount: displayAvailable.size", source)

if __name__ == '__main__':
    unittest.main()
