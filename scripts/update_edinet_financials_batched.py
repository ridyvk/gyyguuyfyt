#!/usr/bin/env python3
"""Incrementally build the EDINET annual financial baseline.

This script is designed for GitHub Actions. It processes only a limited number
of EDINET annual filings per run, commits the partial snapshot, and continues on
the next run. This avoids multi-hour bootstrap jobs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import update_edinet_financials as edinet

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/financials.json"
COMPANY_MASTER = ROOT / "src/data/listedCompanies.json"
SNAPSHOT_SCHEMA_VERSION = 3

STRICT_FACT_NAMES = {
    **edinet.FACT_NAMES,
    "revenue": tuple(
        name
        for name in edinet.FACT_NAMES["revenue"]
        if name != "OrdinaryIncome"
    ),
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_company_codes() -> set[str]:
    payload = load_json(COMPANY_MASTER)
    return {str(company["code"]) for company in payload.get("companies", [])}


def normalize_snapshot(snapshot: dict, current_codes: set[str]) -> dict:
    records = snapshot.get("records", {}) or {}
    snapshot["records"] = {
        str(code): record
        for code, record in records.items()
        if str(code) in current_codes and isinstance(record, dict)
    }
    return snapshot


def annotate_record(record: dict) -> dict:
    record.setdefault("documentType", "AnnualSecuritiesReport")
    record.setdefault("periodType", "annual")
    record.setdefault("sourceDetail", "EDINET有価証券報告書XBRL・年次")
    record.setdefault(
        "quality",
        {
            "policy": "strict-annual-baseline-batched",
            "edinetAnnualReport": True,
            "ambiguousRevenueTagsExcluded": ["OrdinaryIncome"],
        },
    )
    return record


def filing_sort_key(filing: dict) -> tuple[str, str, str]:
    return (
        str(filing.get("periodEnd") or ""),
        str(filing.get("submitDateTime") or ""),
        str(filing.get("docID") or ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-days", type=int, default=460)
    parser.add_argument("--max-documents", type=int, default=350)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()

    api_key = os.environ.get("EDINET_API_KEY", "").strip()
    if not api_key:
        print("EDINET_API_KEY is not configured. Skipping EDINET batched update.")
        return 0

    edinet.FACT_NAMES = STRICT_FACT_NAMES
    snapshot = normalize_snapshot(load_json(SNAPSHOT), load_company_codes())
    records = snapshot.setdefault("records", {})

    filings, scanned = edinet.list_filings(api_key, args.scan_days)
    candidates = []
    for code, filing in filings.items():
        existing = records.get(str(code)) or {}
        if existing.get("source") == "EDINET" and existing.get("documentId") == filing.get("docID"):
            continue
        candidates.append(filing)
    candidates.sort(key=filing_sort_key, reverse=True)
    pending_total = len(candidates)
    batch = candidates[: max(0, args.max_documents)]

    updated = 0
    failures: list[str] = []
    for index, filing in enumerate(batch, 1):
        try:
            archive = edinet.get(f"{edinet.API}/documents/{filing['docID']}?type=1", api_key)
            record = annotate_record(edinet.build_record(filing, edinet.xbrl_from_zip(archive)))
            existing = records.get(record["code"])
            existing_key = (
                str((existing or {}).get("periodEnd") or ""),
                str((existing or {}).get("filedAt") or ""),
            )
            record_key = (record["periodEnd"], record["filedAt"])
            if record.get("metrics") and record_key >= existing_key:
                records[record["code"]] = record
                updated += 1
        except Exception as error:
            failures.append(f"{filing.get('secCode')}:{filing.get('docID')}: {error}")
        if index % 50 == 0:
            print(f"Processed EDINET batch {index}/{len(batch)}")
        time.sleep(args.sleep)

    edinet_count = sum(1 for record in records.values() if record.get("source") == "EDINET")
    tdnet_count = sum(1 for record in records.values() if record.get("source") == "TDnet")
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot.update(
        {
            "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
            "generatedAt": generated_at,
            "source": "EDINET+TDnet" if tdnet_count else "EDINET",
            "status": "building" if pending_total > len(batch) else "ready",
            "message": (
                "EDINET有価証券報告書ベースの年次データを分割更新中。"
                "TDnet通期決算短信は別ステップで直近分のみ上書きします。"
            ),
            "dataPolicy": {
                "mode": "edinet-annual-baseline-batched",
                "baselineSource": "EDINET有価証券報告書XBRL",
                "tdnetOverlay": True,
                "quarterlyMerged": False,
                "note": (
                    "GitHub Actionsの長時間実行を避けるため、EDINET年次データを複数回に分けて構築します。"
                    "OrdinaryIncomeは売上として使いません。"
                ),
            },
            "records": records,
            "stats": {
                **snapshot.get("stats", {}),
                "companies": len(records),
                "edinetCompanies": edinet_count,
                "tdnetCompanies": tdnet_count,
                "edinetDocumentsScanned": scanned,
                "edinetPendingBeforeBatch": pending_total,
                "edinetBatchSize": len(batch),
                "edinetDocumentsUpdated": updated,
                "edinetBatchFailures": len(failures),
                "edinetBatchGeneratedAt": generated_at,
            },
        }
    )
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved annual baseline batch: records={len(records)}, "
        f"EDINET={edinet_count}, TDnet={tdnet_count}, "
        f"pending_before_batch={pending_total}, updated={updated}, failures={len(failures)}."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
