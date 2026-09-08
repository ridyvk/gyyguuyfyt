"""Regression: an empty daily TDnet feed must not erase the EDINET baseline."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_tdnet_financials_overlay_strict as overlay


class FinancialOverlayPreservationTests(unittest.TestCase):
    def test_empty_feed_preserves_both_sources_and_all_existing_metric_values(self):
        records = {
            '7203': {'code': '7203', 'source': 'EDINET', 'documentType': 'AnnualSecuritiesReport', 'periodEnd': '2026-03-31', 'metrics': {'roe': {'value': 14.2}}, 'history': [], 'quality': {}},
            '6758': {'code': '6758', 'source': 'TDnet', 'documentType': 'FullYearEarnings', 'periodEnd': '2026-03-31', 'metrics': {'netMargin': {'value': 8.7}}, 'history': [], 'quality': {}},
        }
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'financials.json'
            snapshot.write_text(json.dumps({'records': records, 'stats': {}}))
            with patch.object(overlay, 'SNAPSHOT', snapshot), patch.object(overlay, 'load_company_codes', return_value=set(records)), patch.object(overlay.strict, 'list_full_year_filings', return_value=({}, {})), patch.object(sys, 'argv', ['overlay', '--backfill-limit', '0']), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(overlay.main(), 0)
            after = json.loads(snapshot.read_text())['records']
            self.assertEqual(after, records)


if __name__ == '__main__':
    unittest.main()
