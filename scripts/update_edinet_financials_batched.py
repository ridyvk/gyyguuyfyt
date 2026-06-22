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
from data_quality import (
    filing_order_key,
    is_unusable_record_validation,
    record_order_key,
    validate_financial_record,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/financials.json"
COMPANY_MASTER = ROOT / "src/data/listedCompanies.json"
GOLDEN_AUDIT = ROOT / "public/data/golden-company-audit.json"
SNAPSHOT_SCHEMA_VERSION = 3
INVENTORY_MODEL_VERSION = 2
DATA_MODEL_VERSION = 9
ROE_MODEL_VERSION = 1
PROVENANCE_MODEL_VERSION = 1
INITIAL_MODEL_CANARY_SIZE = 50

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


def load_missing_golden_codes() -> set[str]:
    payload = load_json(GOLDEN_AUDIT)
    return {
        str(company.get("code") or "")
        for company in payload.get("companies", [])
        if any(
            issue.get("code") == "missing-record"
            for issue in company.get("issues", [])
            if isinstance(issue, dict)
        )
    }


def normalize_snapshot(snapshot: dict, current_codes: set[str]) -> dict:
    records = snapshot.get("records", {}) or {}
    snapshot["records"] = {
        str(code): record
        for code, record in records.items()
        if validate_financial_record(str(code), record, current_codes) is None
    }
    snapshot.setdefault("stats", {})["invalidExistingRecordsDropped"] = (
        len(records) - len(snapshot["records"])
    )
    return snapshot


def annotate_record(record: dict) -> dict:
    record.setdefault("documentType", "AnnualSecuritiesReport")
    record.setdefault("periodType", "annual")
    record.setdefault("sourceDetail", "EDINET有価証券報告書XBRL・年次")
    quality = record.setdefault(
        "quality",
        {
            "policy": "strict-annual-baseline-batched",
            "edinetAnnualReport": True,
            "ambiguousRevenueTagsExcluded": ["OrdinaryIncome"],
        },
    )
    quality["inventoryPolicy"] = "Inventoriesタグを優先し、無い場合は商品・製品、仕掛品、原材料等を合算"
    quality["inventoryModelVersion"] = INVENTORY_MODEL_VERSION
    quality["dataModelVersion"] = DATA_MODEL_VERSION
    quality["roeModelVersion"] = ROE_MODEL_VERSION
    quality["provenanceModelVersion"] = PROVENANCE_MODEL_VERSION
    quality["totalCompanyContextsOnly"] = True
    return record


def filing_sort_key(filing: dict) -> tuple[str, str, str]:
    return filing_order_key(filing)


def record_uses_current_model(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    quality = record.get("quality") or {}
    return int(quality.get("dataModelVersion") or 0) >= DATA_MODEL_VERSION


def record_has_roe_history_mismatch(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    roe = (record.get("metrics") or {}).get("roe") or {}
    history = record.get("history") or []
    if not isinstance(roe, dict) or not isinstance(history, list) or len(history) < 2:
        return False
    previous_value = roe.get("previousValue")
    prior_history_value = (history[-2] or {}).get("roe")
    if not isinstance(previous_value, (int, float)) or not isinstance(
        prior_history_value, (int, float)
    ):
        return False
    return abs(float(previous_value) - float(prior_history_value)) >= 0.05


def record_roe_refresh_priority(record: object) -> int:
    if not isinstance(record, dict):
        return 0
    metric_validation = (
        (record.get("quarantine") or {}).get("metricValidation") or {}
    )
    quarantined_metrics = metric_validation.get("metrics") or {}
    if isinstance(quarantined_metrics, dict) and quarantined_metrics:
        # Re-extract impossible accounting values before ordinary model refreshes.
        return 4
    quality = record.get("quality") or {}
    roe = (record.get("metrics") or {}).get("roe") or {}
    value = roe.get("value") if isinstance(roe, dict) else None
    if (
        int(quality.get("dataModelVersion") or 0) < DATA_MODEL_VERSION
        and isinstance(value, (int, float))
        and abs(float(value)) < 1
    ):
        # A ratio displayed as a percent is a 100x scale error, so repair it first.
        return 3
    if record_has_roe_history_mismatch(record):
        return 2
    return 0

def candidate_priority_key(
    filing: dict,
    records: dict[str, dict],
    missing_golden_codes: set[str] | None = None,
) -> tuple[int, str]:
    code = str(filing.get("_normalizedCode") or "")
    if not code:
        code = edinet.normalize_security_code(filing.get("secCode")) or ""
    if code in (missing_golden_codes or set()) and not records.get(code):
        return (-4, code)
    priority = record_roe_refresh_priority(records.get(code))
    return (-priority, code if priority else "")


def refresh_batch_size(
    max_documents: int,
    data_model_upgraded: bool,
    has_priority_candidates: bool,
) -> int:
    requested = max(0, max_documents)
    if has_priority_candidates:
        # Keep recovery and diagnostics runs short while missing golden cases exist.
        return min(requested, INITIAL_MODEL_CANARY_SIZE)
    return requested


def collect_processed_doc_ids(
    snapshot: dict,
    records: dict[str, dict],
    data_model_upgraded: bool,
) -> set[str]:
    """Return EDINET document IDs already attempted or represented in records.

    When the data model changes, return an empty set so existing EDINET
    filings are reprocessed with the current context and metric policy.
    """
    if data_model_upgraded:
        return set()

    stats = snapshot.get("stats", {}) or {}
    processed = {str(doc_id) for doc_id in stats.get("edinetProcessedDocumentIds", []) if doc_id}
    for record in records.values():
        if not record_uses_current_model(record):
            continue
        if record.get("source") == "EDINET" and record.get("documentId"):
            processed.add(str(record["documentId"]))
        if record.get("edinetBaselineDocumentId"):
            processed.add(str(record["edinetBaselineDocumentId"]))
    return processed


def mark_tdnet_record_with_edinet_baseline(existing: dict, record: dict) -> None:
    """Mark a newer TDnet record as having an EDINET annual baseline processed."""
    existing["edinetBaselineDocumentId"] = record.get("documentId")
    existing["edinetBaselinePeriodEnd"] = record.get("periodEnd")
    existing["edinetBaselineFiledAt"] = record.get("filedAt")
    existing["edinetBaselineSourceUrl"] = record.get("sourceUrl")
    quality = existing.setdefault("quality", {})
    quality["edinetAnnualBaselineProcessed"] = True
    quality["inventoryModelVersion"] = INVENTORY_MODEL_VERSION
    quality["dataModelVersion"] = DATA_MODEL_VERSION


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-days", type=int, default=460)
    parser.add_argument("--max-documents", type=int, default=350)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()

    api_key = os.environ.get("EDINET_API_KEY", "").strip()
    if not api_key:
        print("EDINET_API_KEY is not configured.", file=sys.stderr)
        return 2

    edinet.FACT_NAMES = STRICT_FACT_NAMES
    current_codes = load_company_codes()
    missing_golden_codes = load_missing_golden_codes()
    snapshot = normalize_snapshot(load_json(SNAPSHOT), current_codes)
    records = snapshot.setdefault("records", {})
    stats = snapshot.get("stats", {}) or {}
    data_model_upgraded = int(stats.get("dataModelVersion") or 0) < DATA_MODEL_VERSION
    processed_doc_ids = collect_processed_doc_ids(
        snapshot,
        records,
        data_model_upgraded,
    )

    filings, scanned = edinet.list_filings(api_key, args.scan_days)
    candidates = []
    already_done = 0
    for code, filing in filings.items():
        doc_id = str(filing.get("docID") or "")
        existing = records.get(str(code)) or {}
        if not doc_id or code not in current_codes:
            continue
        if doc_id in processed_doc_ids and existing:
            already_done += 1
            continue
        if (
            existing.get("source") == "EDINET"
            and existing.get("documentId") == doc_id
            and record_uses_current_model(existing)
        ):
            processed_doc_ids.add(doc_id)
            already_done += 1
            continue
        candidates.append({**filing, "_normalizedCode": str(code)})
    candidates.sort(key=filing_sort_key, reverse=True)
    candidates.sort(
        key=lambda filing: candidate_priority_key(
            filing,
            records,
            missing_golden_codes,
        )
    )
    pending_total = len(candidates)
    has_priority_candidates = bool(
        candidates
        and candidate_priority_key(
            candidates[0],
            records,
            missing_golden_codes,
        )[0] < 0
    )
    batch_limit = refresh_batch_size(
        args.max_documents,
        data_model_upgraded,
        has_priority_candidates,
    )
    batch = candidates[:batch_limit]

    updated = 0
    processed_this_batch = 0
    baseline_marked = 0
    no_metrics = 0
    unchanged_documents = 0
    failures: list[str] = []
    for index, filing in enumerate(batch, 1):
        doc_id = str(filing.get("docID") or "")
        try:
            archive = edinet.get(f"{edinet.API}/documents/{filing['docID']}?type=1", api_key)
            record = annotate_record(edinet.build_record(filing, edinet.xbrl_from_zip(archive)))
            processed_doc_ids.add(doc_id)
            processed_this_batch += 1
            existing = records.get(record["code"])
            validation_error = validate_financial_record(
                record["code"], record, current_codes
            )
            if is_unusable_record_validation(validation_error):
                no_metrics += 1
            elif validation_error:
                raise ValueError(f"record validation failed: {validation_error}")
            elif record_order_key(record) >= record_order_key(existing):
                records[record["code"]] = record
                updated += 1
            elif existing and existing.get("source") == "TDnet":
                mark_tdnet_record_with_edinet_baseline(existing, record)
                baseline_marked += 1
            else:
                unchanged_documents += 1
        except Exception as error:
            if is_unusable_record_validation(error):
                processed_doc_ids.add(doc_id)
                processed_this_batch += 1
                no_metrics += 1
            else:
                failures.append(
                    f"{filing.get('secCode')}:{filing.get('docID')}: {error}"
                )
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
            "status": (
                "partial"
                if failures
                else "building" if pending_total > len(batch) else "ready"
            ),
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
                    "一度処理したEDINET書類IDを記録し、同じXBRLを繰り返し処理しません。"
                    "OrdinaryIncomeは売上として使いません。"
                    "棚卸資産はInventoriesタグを優先し、無い場合は商品・製品、仕掛品、原材料等を合算します。"
                    "全社実績コンテキストだけを採用し、セグメント軸と予想値を除外します。"
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
                "edinetDocumentsProcessedThisBatch": processed_this_batch,
                "edinetDocumentsAlreadyProcessed": already_done,
                "edinetTdnetBaselineMarked": baseline_marked,
                "edinetNoMetricDocuments": no_metrics,
                "edinetDocumentsUnchanged": unchanged_documents,
                "edinetProcessedDocumentIds": sorted(processed_doc_ids),
                "edinetBatchFailures": len(failures),
                "edinetBatchGeneratedAt": generated_at,
                "inventoryModelVersion": INVENTORY_MODEL_VERSION,
                "dataModelVersion": DATA_MODEL_VERSION,
                "dataModelRefresh": data_model_upgraded,
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
        f"pending_before_batch={pending_total}, processed={processed_this_batch}, "
        f"updated={updated}, tdnet_baseline_marked={baseline_marked}, "
        f"failures={len(failures)}, data_model_refresh={data_model_upgraded}."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
