from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_disclosures


class DisclosureClassificationTests(unittest.TestCase):
    def test_high_impact_title_signals_are_explainable(self) -> None:
        cases = [
            (
                "通期業績予想の上方修正及び増配に関するお知らせ",
                "guidance",
                "critical",
                {"業績見通しを上方修正", "配当予想を増額"},
            ),
            (
                "業績予想の下方修正及び特別損失の計上に関するお知らせ",
                "guidance",
                "critical",
                {"業績見通しを下方修正", "特別損失・減損の計上"},
            ),
            (
                "自己株式の取得に係る事項の決定に関するお知らせ",
                "buyback",
                "high",
                {"自己株式の取得を公表"},
            ),
            (
                "第三者割当による新株式発行に関するお知らせ",
                "capital",
                "critical",
                {"新株発行による希薄化可能性"},
            ),
        ]
        for title, category, importance, labels in cases:
            with self.subTest(title=title):
                result = update_disclosures.classify_title(title)
                self.assertEqual(result["category"], category)
                self.assertEqual(result["importance"], importance)
                self.assertTrue(
                    labels.issubset({signal["label"] for signal in result["signals"]})
                )
                self.assertTrue(
                    all(signal["basis"] == "title" for signal in result["signals"])
                )

    def test_correction_is_flagged_without_claiming_numeric_diff(self) -> None:
        result = update_disclosures.classify_title(
            "（訂正・数値データ訂正）2026年3月期 決算短信の一部訂正について"
        )
        self.assertTrue(result["isCorrection"])
        self.assertIn(
            "過去開示を訂正・差替え",
            {signal["label"] for signal in result["signals"]},
        )
        self.assertNotIn("%", result["summary"])

    def test_routine_equity_compensation_is_not_critical_dilution(self) -> None:
        result = update_disclosures.classify_title(
            "譲渡制限付株式報酬としての新株式発行に関するお知らせ"
        )
        self.assertEqual(result["category"], "capital")
        self.assertEqual(result["importance"], "medium")
        self.assertIn(
            "株式報酬・インセンティブ制度",
            {signal["label"] for signal in result["signals"]},
        )


class TDnetDisclosureParserTests(unittest.TestCase):
    def test_parser_keeps_pdf_only_rows(self) -> None:
        html = b"""
        <table><tr>
          <td class="kjTime">15:00</td>
          <td class="kjCode">7203</td>
          <td class="kjName">Example</td>
          <td class="kjTitle"><a href="140120260101000001.pdf">Notice</a></td>
          <td class="kjXbrl"></td>
        </tr></table>
        """
        rows, pages = update_disclosures.parse_tdnet_page(html)
        self.assertEqual(pages, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["titleHref"], "140120260101000001.pdf")
        self.assertNotIn("xbrlHref", rows[0])


class DisclosureComparisonTests(unittest.TestCase):
    def test_same_category_events_link_to_previous_disclosure(self) -> None:
        now = datetime.now(update_disclosures.JST).replace(microsecond=0)
        events = [
            update_disclosures.make_event(
                source="TDnet",
                document_id="old",
                code="7203",
                company_name="Example",
                filed_at=now - timedelta(days=10),
                title="通期業績予想の修正に関するお知らせ",
                url="https://example.com/old.pdf",
            ),
            update_disclosures.make_event(
                source="TDnet",
                document_id="new",
                code="7203",
                company_name="Example",
                filed_at=now,
                title="通期業績予想の上方修正に関するお知らせ",
                url="https://example.com/new.pdf",
            ),
        ]
        snapshot = update_disclosures.build_snapshot(
            events,
            retention_days=120,
            source_status={
                "TDnet": {"status": "ready"},
                "EDINET": {"status": "ready"},
            },
            scanned={"TDnet": 2, "EDINET": 0},
        )
        newest = snapshot["events"][0]
        self.assertEqual(newest["previousComparableId"], "tdnet:old")
        self.assertEqual(newest["daysSincePrevious"], 10)


if __name__ == "__main__":
    unittest.main()
