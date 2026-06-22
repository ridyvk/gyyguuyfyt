from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-pages.yml'


class PagesWorkflowGuardTests(unittest.TestCase):
    def test_deploy_pages_does_not_run_on_financial_workflow_completion(self) -> None:
        source = DEPLOY_WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('push:', source)
        self.assertIn('workflow_dispatch:', source)
        self.assertNotIn('workflow_run:', source)
        self.assertNotIn('Update annual financials', source)
        self.assertNotIn('Update market prices', source)


if __name__ == '__main__':
    unittest.main()
