#!/usr/bin/env python3
"""Finalize KPI Scope snapshot as EDINET annual baseline + TDnet annual overlay."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/financials.json"
STATUS = ROOT / "public/data/update-status.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_annual_record(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    if record.get("source") == "EDINET":
        return True
    return record.get("source") == "TDnet" and record.get("documentType") == "FullYearEarnings"


def main() -> int:
    generated_at = utc_now()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    original_records = snapshot.get("records", {}) or {}
    annual_records = {
        str(code): record
        for code, record in original_records.items()
        if is_annual_record(record)
    }
    dropped = len(original_records) - len(annual_records)
    edinet_count = sum(1 for record in annual_records.values() if record.get("source") == "EDINET")
    tdnet_count = sum(1 for record in annual_records.values() if record.get("source") == "TDnet")

    stats = {**snapshot.get("stats", {})}
    stats.update(
        {
            "companies": len(annual_records),
            "edinetCompanies": edinet_count,
            "tdnetCompanies": tdnet_count,
            "annualOnly": True,
            "nonAnnualRecordsDropped": dropped,
        }
    )

    snapshot.update(
        {
            "generatedAt": generated_at,
            "source": "EDINET+TDnet",
            "status": "ready",
            "message": (
                "EDINET有価証券報告書ベースの年次データを基礎DBにし、"
                "TDnetの通期決算短信で直近分のみ上書きしています。"
                "四半期・中間短信は統合していません。"
            ),
            "dataPolicy": {
                "mode": "edinet-annual-baseline-tdnet-full-year-overlay",
                "baselineSource": "EDINET有価証券報告書XBRL",
                "overlaySource": "TDnet通期決算短信XBRL",
                "edinetMerged": True,
                "tdnetOverlay": True,
                "quarterlyMerged": False,
                "note": (
                    "上場全社級のカバレッジを確保するため、EDINET年次データを基礎DBとして使います。"
                    "TDnetは通期決算短信だけを採用し、四半期・中間短信は年次KPIとの混在を避けるため除外します。"
                ),
            },
            "records": annual_records,
            "stats": stats,
        }
    )

    status = {
        "generatedAt": generated_at,
        "mode": "edinet-annual-baseline-tdnet-full-year-overlay",
        "source": "EDINET+TDnet",
        "baselineSource": "EDINET有価証券報告書XBRL",
        "overlaySource": "TDnet通期決算短信XBRL",
        "edinetMerged": True,
        "tdnetOverlay": True,
        "quarterlyMerged": False,
        "companies": len(annual_records),
        "edinetCompanies": edinet_count,
        "tdnetCompanies": tdnet_count,
        "nonAnnualRecordsDropped": dropped,
        "tdnetRowsScanned": stats.get("tdnetRowsScanned", 0),
        "tdnetEarningsRows": stats.get("tdnetEarningsRows", 0),
        "tdnetQuarterlyRowsSkipped": stats.get("tdnetQuarterlyRowsSkipped", 0),
        "tdnetFullYearFilings": stats.get("tdnetFullYearFilings", 0),
        "tdnetDocumentsUpdated": stats.get("tdnetDocumentsUpdated", 0),
        "tdnetStrictFailures": stats.get("tdnetStrictFailures", 0),
        "message": "EDINET年次ベースライン＋TDnet通期決算短信オーバーレイで更新中。四半期・中間短信は統合していません。",
    }

    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    STATUS.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Finalized annual dataset: "
        f"{len(annual_records)} companies, EDINET {edinet_count}, TDnet {tdnet_count}, "
        f"dropped {dropped} non-annual records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
