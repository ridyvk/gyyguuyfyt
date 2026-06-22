from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / 'src' / 'pages' / 'Universe.tsx'


class UniversePartialStatusGuardTests(unittest.TestCase):
    def test_partial_and_building_statuses_are_displayed_as_usable_coverage(self) -> None:
        source = UNIVERSE.read_text(encoding='utf-8')
        self.assertIn("status === 'ready' || status === 'partial' || status === 'building'", source)
        self.assertIn("financialUsable", source)
        self.assertIn("missingCompanies", source)
        self.assertIn("coverageRatio", source)
        self.assertIn("一部更新中", source)
        self.assertIn("構築中", source)
        self.assertNotIn("financialSnapshot?.status === 'ready'\n                ? `EDINET・TDnet", source)


if __name__ == '__main__':
    unittest.main()
