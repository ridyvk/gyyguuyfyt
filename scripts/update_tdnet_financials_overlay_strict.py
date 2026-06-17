#!/usr/bin/env python3
"""Overlay strict full-year TDnet earnings onto the EDINET annual baseline."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import update_tdnet_financials_strict as strict
from update_tdnet_financials import COMPANY_MASTER, SNAPSHOT, get

# Compatibility patch for the first strict updater version.
strict.timedelta = timedelta


def should_keep_existing(code: str, record: dict, current_codes: set[str]) -> bool:
    if code not in current_codes or not isinstance(record, dict):
        return False
    if record.get("source") == "EDINET":
        return True
    return record.get("source") == "TDnet" and record.get("documentType") == "FullYearEarnings"


def should_replace(existing: dict | None, record: dict) -> bool:
    if existing is None:
        return True
    old_key = (str(existing.get("periodEnd") or ""), str(existing.get("filedAt") or ""))
    return (record["periodEnd"], record["filedAt"]) >= old_key


def load_company_codes() -> set[str]:
    payload = json.loads(COMPANY_MASTER.read_text(encoding="utf-8"))
    return {str(company["code"]) for company in payload.get("companies", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=31)
    parser.add_argument("--max-documents", type=int, default=1500)
    args = parser.parse_args()

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current_codes = load_company_codes()
    old_records = snapshot.get("records", {}) or {}
    records = {
        str(code): record
        for code, record in old_records.items()
        if should_keep_existing(str(code), record, current_codes)
    }
    dropped_existing = len(old_records) - len(records)

    filings, scan_stats = strict.list_full_year_filings(args.lookback_days)
    updated = 0
    failures: list[str] = []
    candidates = list(filings.values())[: args.max_documents]
    for index, filing in enumerate(candidates, 1):
        try:
            record = strict.build_record(filing, get(filing["xbrlUrl"]))
            if (record.get("metrics") or record.get("valuation")) and should_replace(
                records.get(record["code"]),
                record,
            ):
                records[record["code"]] = record
                updated += 1
        except Exception as error:
            failures.append(f"{filing.get('code')}:{filing.get('documentId')}: {error}")
        if index % 50 == 0:
            print(f"Processed {index}/{len(candidates)}")
        time.sleep(0.06)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    edinet_count = sum(1 for record in records.values() if record.get("source") == "EDINET")
    tdnet_count = sum(1 for record in records.values() if record.get("source") == "TDnet")
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
            "records": records,
            "stats": {
                **snapshot.get("stats", {}),
                **scan_stats,
                "companies": len(records),
                "edinetCompanies": edinet_count,
                "tdnetCompanies": tdnet_count,
                "tdnetDocumentsUpdated": updated,
                "tdnetStrictFailures": len(failures),
                "nonAnnualExistingRecordsDropped": dropped_existing,
            },
        }
    )
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(records)} annual companies; "
        f"EDINET {edinet_count}, TDnet {tdnet_count}; "
        f"TDnet updated {updated}; failures {len(failures)}."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
