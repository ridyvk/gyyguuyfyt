#!/usr/bin/env python3
"""Finalize KPI Scope snapshot as a strict TDnet full-year dataset."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/financials.json"
STATUS = ROOT / "public/data/update-status.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    generated_at = utc_now()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    original_records = snapshot.get("records", {}) or {}

    strict_records = {
        str(code): record
        for code, record in original_records.items()
        if isinstance(record, dict)
        and record.get("source") == "TDnet"
        and record.get("documentType") == "FullYearEarnings"
    }
    dropped = len(original_records) - len(strict_records)

    stats = {**snapshot.get("stats", {})}
    stats.update(
        {
            "companies": len(strict_records),
            "tdnetOnly": True,
            "acceptedDocumentType": "FullYearEarnings",
            "nonStrictRecordsDropped": dropped,
        }
    )

    snapshot.update(
        {
            "generatedAt": generated_at,
            "source": "TDnet",
            "status": "ready",
            "message": (
                "TDnet決算短信ベースで更新中。"
                "四半期・中間短信とEDINET有価証券報告書データは統合していません。"
            ),
            "dataPolicy": {
                "mode": "tdnet-only-full-year-strict",
                "primarySource": "TDnet決算短信XBRL",
                "acceptedDocumentType": "FullYearEarnings",
                "edinetMerged": False,
                "quarterlyMerged": False,
                "note": (
                    "年次KPIの齟齬を減らすため、TDnetの通期決算短信のみを公開します。"
                    "四半期・中間短信は対象期と年次KPIの混在を避けるため除外します。"
                ),
            },
            "records": strict_records,
            "stats": stats,
        }
    )

    status = {
        "generatedAt": generated_at,
        "mode": "tdnet-only-full-year-strict",
        "source": "TDnet",
        "acceptedDocumentType": "FullYearEarnings",
        "edinetMerged": False,
        "quarterlyMerged": False,
        "companies": len(strict_records),
        "nonStrictRecordsDropped": dropped,
        "tdnetRowsScanned": stats.get("tdnetRowsScanned", 0),
        "tdnetEarningsRows": stats.get("tdnetEarningsRows", 0),
        "tdnetQuarterlyRowsSkipped": stats.get("tdnetQuarterlyRowsSkipped", 0),
        "tdnetFullYearFilings": stats.get("tdnetFullYearFilings", 0),
        "tdnetDocumentsUpdated": stats.get("tdnetDocumentsUpdated", 0),
        "tdnetStrictFailures": stats.get("tdnetStrictFailures", 0),
        "message": "TDnetの通期決算短信のみで更新中。四半期・中間短信とEDINETは統合していません。",
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
        "Finalized strict TDnet snapshot: "
        f"{len(strict_records)} full-year records, dropped {dropped} non-strict records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
