from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import update_edinet_financials_batched as batched
import update_edinet_financials_batched_equity_v10 as equity_v10

WORKFLOW = ROOT / '.github' / 'workflows' / 'update-financials.yml'


class EdinetEquityDenominatorPriorityTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Keep module globals deterministic for later tests in the same process.
        batched.DATA_MODEL_VERSION = 9

    def test_wrapper_prefers_net_assets_before_shareholders_equity(self) -> None:
        equity_v10.install_equity_priority()
        equity_names = batched.STRICT_FACT_NAMES['equity']
        self.assertLess(equity_names.index('NetAssets'), equity_names.index('ShareholdersEquity'))
        self.assertLess(
            equity_names.index('NetAssetsSummaryOfBusinessResults'),
            equity_names.index('ShareholdersEquity'),
        )
        self.assertEqual(batched.DATA_MODEL_VERSION, 10)

    def test_financial_workflow_uses_equity_priority_wrapper(self) -> None:
        source = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('scripts/update_edinet_financials_batched_equity_v10.py', source)
        self.assertNotIn('python scripts/update_edinet_financials_batched.py \\', source)


if __name__ == '__main__':
    unittest.main()
