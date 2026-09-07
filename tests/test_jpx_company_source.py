from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_jpx_companies


class JpxCompanySourceTests(unittest.TestCase):
    def test_discovers_current_xlsx_link(self) -> None:
        source = (
            '<a href="/markets/statistics-equities/misc/'
            'tvdivq0000001vg2-att/data_j.xlsx">一覧</a>'
        )

        self.assertEqual(
            update_jpx_companies.discover_source_url(source),
            update_jpx_companies.FALLBACK_SOURCE_URL,
        )

    def test_accepts_legacy_xls_link(self) -> None:
        source = (
            '<a href="/markets/statistics-equities/misc/'
            'tvdivq0000001vg2-att/data_j.xls">一覧</a>'
        )

        self.assertTrue(
            update_jpx_companies.discover_source_url(source).endswith("data_j.xls")
        )

    def test_rejects_page_without_company_workbook(self) -> None:
        with self.assertRaisesRegex(ValueError, "workbook link was not found"):
            update_jpx_companies.discover_source_url("<html></html>")


if __name__ == "__main__":
    unittest.main()
