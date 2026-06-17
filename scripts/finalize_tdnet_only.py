#!/usr/bin/env python3
"""Finalize KPI Scope snapshot as a TDnet-only MVP dataset."""

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

    tdnet_records = {
        str(code): record
        for code, record in original_records.items()
        if isinstance(record, dict) and record.get("source") == "TDnet"
    }
    dropped = len(original_records) - len(tdnet_records)

    stats = {**snapshot.get("stats", {})}
    stats.update(
        {
            "companies": len(tdnet_records),
            "tdnetOnly": True,
            "nonTdnetRecordsDropped": dropped,
        }
    )

    snapshot.update(
        {
            "generatedAt": generated_at,
            "source": "TDnet",
            "status": "ready",
            "message": (
                "TDnet決算短信ベースで更新中。"
                "EDINET有価証券報告書データとは統合していません。"
            ),
            "dataPolicy": {
                "mode": "tdnet-only-mvp",
                "primarySource": "TDnet決算短信XBRL",
                "edinetMerged": False,
                "note": (
                    "速報KPIの齟齬を減らすため、当面はTDnetレコードのみを公開します。"
                    "EDINETは有報ベースの確定値確認用として、将来別レイヤーで扱います。"
                ),
            },
            "records": tdnet_records,
            "stats": stats,
        }
    )

    status = {
        "generatedAt": generated_at,
        "mode": "tdnet-only-mvp",
        "source": "TDnet",
        "edinetMerged": False,
        "companies": len(tdnet_records),
        "nonTdnetRecordsDropped": dropped,
        "tdnetDocumentsScanned": stats.get("tdnetDocumentsScanned", 0),
        "tdnetDocumentsUpdated": stats.get("tdnetDocumentsUpdated", 0),
        "message": "TDnet決算短信ベースで更新中。EDINETとは統合していません。",
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
        "Finalized TDnet-only snapshot: "
        f"{len(tdnet_records)} TDnet records, dropped {dropped} non-TDnet records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
