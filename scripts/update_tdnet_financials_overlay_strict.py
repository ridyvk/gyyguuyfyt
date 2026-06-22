#!/usr/bin/env python3
"""Overlay strict full-year TDnet earnings onto the EDINET annual baseline."""

from __future__ import annotations

from copy import deepcopy
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import update_tdnet_financials_strict as strict
from update_tdnet_financials import COMPANY_MASTER, SNAPSHOT, get
from data_quality import (
    is_unusable_record_validation,
    quarantine_invalid_metrics,
    record_order_key,
    validate_financial_record,
)
from reconcile_financial_sources import (
    reconcile_same_period,
    reconciliation_totals,
)

# Compatibility patch for the first strict updater version.
strict.timedelta = timedelta


def should_keep_existing(code: str, record: dict, current_codes: set[str]) -> bool:
    if code not in current_codes or not isinstance(record, dict):
        return False
    if record.get("source") == "EDINET":
        return True
    return record.get("source") == "TDnet" and record.get("documentType") == "FullYearEarnings"


def merge_correction_record(base: dict, correction: dict) -> dict:
    """Overlay a partial correction XBRL onto its complete same-period filing."""
    if base.get("periodEnd") != correction.get("periodEnd"):
        raise ValueError("correction and base filing periods do not match")

    merged = deepcopy(base)
    for key in (
        "companyName",
        "documentId",
        "documentType",
        "filedAt",
        "periodEnd",
        "periodType",
        "source",
        "sourceDetail",
        "sourceUrl",
        "title",
    ):
        if correction.get(key) is not None:
            merged[key] = correction[key]

    merged["metrics"] = {
        **deepcopy(base.get("metrics") or {}),
        **deepcopy(correction.get("metrics") or {}),
    }
    if base.get("valuation") or correction.get("valuation"):
        merged["valuation"] = {
            **deepcopy(base.get("valuation") or {}),
            **deepcopy(correction.get("valuation") or {}),
        }

    points: dict[str, dict] = {}
    for point in base.get("history") or []:
        if isinstance(point, dict) and point.get("year"):
            points[str(point["year"])] = deepcopy(point)
    for point in correction.get("history") or []:
        if isinstance(point, dict) and point.get("year"):
            year = str(point["year"])
            points[year] = {**points.get(year, {}), **deepcopy(point)}
    merged["history"] = [points[year] for year in sorted(points)[-3:]]

    for metric_key in (
        "operatingMargin",
        "netMargin",
        "roe",
        "operatingCfMargin",
    ):
        metric = merged["metrics"].get(metric_key)
        if not isinstance(metric, dict):
            continue
        trend = [
            point[metric_key]
            for point in merged["history"]
            if isinstance(point.get(metric_key), (int, float))
        ]
        if len(trend) >= 2:
            metric["trend"] = trend
        else:
            metric.pop("trend", None)

    quality = {
        **deepcopy(base.get("quality") or {}),
        **deepcopy(correction.get("quality") or {}),
        "correctionMergeModelVersion": 1,
        "correctionStatus": "merged-with-base-filing",
        "correctionBaseDocumentId": base.get("documentId"),
        "correctionBaseSourceUrl": base.get("sourceUrl"),
        "correctionDocumentId": correction.get("documentId"),
    }
    merged["quality"] = quality
    return merged


def build_complete_record(filing: dict) -> tuple[dict, bool]:
    correction = strict.build_record(filing, get(filing["xbrlUrl"]))
    if not strict.is_correction_title(filing.get("title", "")):
        return correction, False

    same_period: list[dict] = []
    for previous_filing in filing.get("_previousFilings") or []:
        try:
            previous_record = strict.build_record(
                previous_filing,
                get(previous_filing["xbrlUrl"]),
            )
        except Exception:
            continue
        if previous_record.get("periodEnd") == correction.get("periodEnd"):
            same_period.append(previous_record)

    if not same_period:
        quality = correction.setdefault("quality", {})
        quality["correctionStatus"] = "base-filing-not-found"
        return correction, False

    chain = sorted(
        [*same_period, correction],
        key=lambda record: (
            str(record.get("filedAt") or ""),
            str(record.get("documentId") or ""),
        ),
    )
    merged = chain[0]
    for next_record in chain[1:]:
        merged = merge_correction_record(merged, next_record)
    return merged, True


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


def has_metric_validation_quarantine(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    metric_validation = (
        (record.get("quarantine") or {}).get("metricValidation") or {}
    )
    metrics = metric_validation.get("metrics") or {}
    return isinstance(metrics, dict) and bool(metrics)


def select_candidates(
    filings: dict[str, dict],
    records: dict[str, dict],
    lookback_days: int,
    backfill_limit: int,
    max_documents: int,
    attempted_document_ids: set[str] | None = None,
    priority_codes: list[str] | None = None,
) -> list[dict]:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=max(0, lookback_days))
    ).date().isoformat()
    priority = set(priority_codes or [])
    recovery_codes = priority | {
        code
        for code, record in records.items()
        if has_metric_validation_quarantine(record)
    }
    recovery = [
        filing
        for code, filing in filings.items()
        if code in recovery_codes
    ]
    recovery.sort(key=lambda filing: str(filing.get("code") or ""))
    selected_recovery_codes = {
        str(filing.get("code") or "") for filing in recovery
    }
    recent = [
        filing
        for filing in filings.values()
        if str(filing.get("filedAt") or "")[:10] >= cutoff
        and str(filing.get("code") or "") not in selected_recovery_codes
    ]
    recent_codes = selected_recovery_codes | {
        str(filing.get("code") or "") for filing in recent
    }

    backfill_pool = []
    ordered_codes = sorted(
        filings,
        key=lambda code: (
            not any(character.isalpha() for character in code),
            code,
        ),
    )
    for code in ordered_codes:
        if code in recent_codes:
            continue
        filing = filings[code]
        existing = records.get(code) or {}
        quality = existing.get("quality") or {}
        if (
            existing.get("source") == "EDINET"
            and not quality.get("roeDocumentId")
        ):
            backfill_pool.append(filing)

    backfill_pool.sort(
        key=lambda filing: str(filing.get("code") or "") not in priority
    )

    attempted = attempted_document_ids if attempted_document_ids is not None else set()
    unseen = [
        filing
        for filing in backfill_pool
        if str(filing.get("documentId") or "") not in attempted
    ]
    if not unseen and backfill_pool:
        attempted.clear()
        unseen = backfill_pool
    backfill = unseen[: max(0, backfill_limit)]

    combined = recovery + recent + backfill
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
    parser.add_argument("--priority-code", action="append", default=[])
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
    updated = 0
    roe_enriched = 0
    reconciled_companies = 0
    matched_metrics = 0
    quarantined_metrics = 0
    correction_records_merged = 0
    no_metric_documents = 0
    metric_quarantines = 0
    failures: list[str] = []
    eligible_filings = {
        code: filing
        for code, filing in filings.items()
        if code in current_codes
    }
    attempted_document_ids = set(
        snapshot.get("stats", {}).get("tdnetRoeBackfillAttemptedDocumentIds", [])
    )
    candidates = select_candidates(
        eligible_filings,
        records,
        args.lookback_days,
        args.backfill_limit,
        args.max_documents,
        attempted_document_ids,
        args.priority_code,
    )
    for index, filing in enumerate(candidates, 1):
        try:
            record, correction_merged = build_complete_record(filing)
            if correction_merged:
                correction_records_merged += 1
            metric_quarantines += quarantine_invalid_metrics(record)
            validation_error = validate_financial_record(
                record["code"], record, current_codes
            )
            if is_unusable_record_validation(validation_error):
                no_metric_documents += 1
            else:
                if validation_error:
                    raise ValueError(
                        "TDnet record did not pass annual-record validation: "
                        f"{validation_error}"
                    )
                existing = records.get(record["code"])
                reconciliation = (
                    reconcile_same_period(existing, record)
                    if existing and record.get("metrics")
                    else None
                )
                if reconciliation is not None:
                    reconciled_companies += 1
                    matched_metrics += reconciliation.matched
                    quarantined_metrics += reconciliation.quarantined
                    if (
                        (existing.get("quality") or {}).get("roeDocumentId")
                        == record.get("documentId")
                    ):
                        roe_enriched += 1
                elif record.get("metrics") and should_replace(existing, record):
                    records[record["code"]] = record
                    updated += 1
        except Exception as error:
            failures.append(f"{filing.get('code')}:{filing.get('documentId')}: {error}")
        finally:
            document_id = str(filing.get("documentId") or "")
            if document_id:
                attempted_document_ids.add(document_id)
        if index % 50 == 0:
            print(f"Processed {index}/{len(candidates)}")
        time.sleep(0.06)

    unresolved_document_ids = {
        str(filing.get("documentId") or "")
        for code, filing in eligible_filings.items()
        if records.get(code, {}).get("source") == "EDINET"
        and not (records.get(code, {}).get("quality") or {}).get("roeDocumentId")
    }
    attempted_document_ids.intersection_update(unresolved_document_ids)

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
                "tdnetCorrectionRecordsMerged": correction_records_merged,
                "sourceReconciliationChecksThisRun": reconciled_companies,
                "sourceMatchedMetricsThisRun": matched_metrics,
                "sourceQuarantinedMetricsThisRun": quarantined_metrics,
                **reconciliation_totals(records),
                "tdnetRoeBackfillAttemptedDocumentIds": sorted(attempted_document_ids),
                "tdnetRoePriorityCodesMissing": sorted(
                    set(args.priority_code) - set(eligible_filings)
                ),
                "tdnetDocumentsAttempted": len(candidates),
                "tdnetStrictFailures": len(failures),
                "tdnetStrictFailureDetails": failures[:30],
                "tdnetMetricsQuarantined": metric_quarantines,
                "tdnetNoMetricDocuments": no_metric_documents,
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
        f"TDnet updated {updated}; reconciled {reconciled_companies}; "
        f"matched metrics {matched_metrics}; quarantined metrics {quarantined_metrics}; "
        f"ROE enriched {roe_enriched}; corrections merged "
        f"{correction_records_merged}; no-metric documents "
        f"{no_metric_documents}; failures {len(failures)}."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
