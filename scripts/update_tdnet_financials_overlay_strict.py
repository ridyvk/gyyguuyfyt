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
from data_quality import record_order_key, validate_financial_record

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
    return record_order_key(record) >= record_order_key(existing)


def merge_same_period_disclosed_roe(existing: dict | None, record: dict) -> bool:
    """Merge TDnet's displayed ROE into a newer EDINET record for the same year."""
    if not existing or existing.get("periodEnd") != record.get("periodEnd"):
        return False
    tdnet_roe = (record.get("metrics") or {}).get("roe") or {}
    if not all(
        isinstance(tdnet_roe.get(key), (int, float))
        for key in ("value", "previousValue")
    ):
        return False

    existing_metrics = existing.setdefault("metrics", {})
    existing_metrics["roe"] = {
        key: list(value) if isinstance(value, list) else value
        for key, value in tdnet_roe.items()
    }

    tdnet_history = {
        point.get("year"): point.get("roe")
        for point in record.get("history", [])
        if point.get("year") and isinstance(point.get("roe"), (int, float))
    }
    for point in existing.get("history", []):
        year = point.get("year")
        if year in tdnet_history:
            point["roe"] = tdnet_history[year]

    quality = existing.setdefault("quality", {})
    quality.update(
        {
            "roeSource": "TDnet通期決算短信XBRL",
            "roeSourceUrl": record.get("sourceUrl"),
            "roeDocumentId": record.get("documentId"),
        }
    )
    return True


def select_candidates(
    filings: dict[str, dict],
    records: dict[str, dict],
    lookback_days: int,
    backfill_limit: int,
    max_documents: int,
) -> list[dict]:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=max(0, lookback_days))
    ).date().isoformat()
    recent = [
        filing
        for filing in filings.values()
        if str(filing.get("filedAt") or "")[:10] >= cutoff
    ]
    recent_codes = {str(filing.get("code") or "") for filing in recent}

    backfill = []
    for code in sorted(filings):
        if code in recent_codes or len(backfill) >= max(0, backfill_limit):
            continue
        filing = filings[code]
        existing = records.get(code) or {}
        quality = existing.get("quality") or {}
        if (
            existing.get("source") == "EDINET"
            and existing.get("periodEnd") == filing.get("periodEnd")
            and not quality.get("roeDocumentId")
        ):
            backfill.append(filing)

    combined = recent + backfill
    return combined[: max(0, max_documents)]


def load_company_codes() -> set[str]:
    payload = json.loads(COMPANY_MASTER.read_text(encoding="utf-8"))
    return {str(company["code"]) for company in payload.get("companies", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=31)
    parser.add_argument("--backfill-lookback-days", type=int, default=460)
    parser.add_argument("--backfill-limit", type=int, default=50)
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

    filings, scan_stats = strict.list_full_year_filings(
        max(args.lookback_days, args.backfill_lookback_days)
    )
    for filing in filings.values():
        filing["periodEnd"] = str(filing.get("periodEnd") or "")
    updated = 0
    roe_enriched = 0
    failures: list[str] = []
    eligible_filings = {
        code: filing
        for code, filing in filings.items()
        if code in current_codes
    }
    candidates = select_candidates(
        eligible_filings,
        records,
        args.lookback_days,
        args.backfill_limit,
        args.max_documents,
    )
    for index, filing in enumerate(candidates, 1):
        try:
            record = strict.build_record(filing, get(filing["xbrlUrl"]))
            if validate_financial_record(record["code"], record, current_codes) is not None:
                raise ValueError("TDnet record did not pass annual-record validation")
            existing = records.get(record["code"])
            if record.get("metrics") and should_replace(existing, record):
                records[record["code"]] = record
                updated += 1
            elif record.get("metrics") and merge_same_period_disclosed_roe(
                existing,
                record,
            ):
                roe_enriched += 1
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
                "tdnetRoeDisclosuresMerged": roe_enriched,
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
        f"TDnet updated {updated}; ROE enriched {roe_enriched}; "
        f"failures {len(failures)}."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
