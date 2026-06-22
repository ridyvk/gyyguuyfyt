from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-pages.yml'


class PagesWorkflowGuardTests(unittest.TestCase):
    def test_deploy_pages_runs_after_successful_data_workflows(self) -> None:
        source = DEPLOY_WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('push:', source)
        self.assertIn('workflow_dispatch:', source)
        self.assertIn('workflow_run:', source)
        self.assertIn('Update annual financials', source)
        self.assertIn('Update market prices', source)
        self.assertIn(
            "github.event.workflow_run.conclusion == 'success'",
            source,
        )
        self.assertIn('group: pages', source)
        self.assertIn('cancel-in-progress: true', source)
        self.assertIn('ref: main', source)


if __name__ == '__main__':
    unittest.main()
