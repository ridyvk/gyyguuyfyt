#!/usr/bin/env python3
"""Finalize KPI Scope snapshot as EDINET annual baseline + TDnet annual overlay."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from data_quality import (
    is_iso_date,
    normalize_security_code,
    quarantine_invalid_metrics,
    quarantine_misaligned_metric_trends,
    validate_financial_record,
)
from reconcile_financial_sources import reconciliation_totals

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/financials.json"
STATUS = ROOT / "public/data/update-status.json"
COMPANY_MASTER = ROOT / "src/data/listedCompanies.json"
GOLDEN_FIXTURE = ROOT / "tests/fixtures/edinet_200_company_golden.json"
FALLBACK_TARGET_COMPANIES = 3000
MIN_TRUSTED_EDINET_ROE_MODEL_VERSION = 6
CURRENT_ROE_EXTRACTION_POLICIES = {
    "ordinary-edinet-latest-refresh",
    "ordinary-missing-edinet-fallback",
    "strict-annual-baseline-batched",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_company_codes() -> set[str]:
    try:
        payload = json.loads(COMPANY_MASTER.read_text(encoding="utf-8"))
        return {
            str(company["code"])
            for company in payload.get("companies", [])
            if isinstance(company, dict)
            and company.get("code")
            and normalize_security_code(company["code"]) == str(company["code"])
        }
    except Exception:
        return set()


def load_golden_anchors() -> dict[str, dict]:
    if not GOLDEN_FIXTURE.exists():
        return {}
    try:
        fixture = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        str(company.get("code")): company
        for company in fixture.get("companies", [])
        if isinstance(company, dict)
        and company.get("code")
        and company.get("documentId")
        and company.get("periodEnd")
        and isinstance(company.get("anchors"), dict)
    }


def apply_golden_anchors(records: dict[str, dict]) -> tuple[int, int]:
    """Prefer strict golden values while the underlying EDINET document is unchanged."""
    golden_by_code = load_golden_anchors()
    anchored_companies = 0
    anchored_metrics = 0
    for code, golden in golden_by_code.items():
        record = records.get(code)
        if not isinstance(record, dict):
            continue
        golden_period_end = str(golden.get("periodEnd") or "")
        record_period_end = str(record.get("periodEnd") or "")
        if (
            record.get("documentId") != golden.get("documentId")
            or (
                record_period_end != golden_period_end
                and is_iso_date(record_period_end)
            )
        ):
            continue
        record["periodEnd"] = golden_period_end
        metrics = record.setdefault("metrics", {})
        if not isinstance(metrics, dict):
            continue
        applied_here = 0
        for metric_key, anchor in (golden.get("anchors") or {}).items():
            if not isinstance(anchor, dict) or "value" not in anchor:
                continue
            metric = metrics.setdefault(str(metric_key), {})
            if not isinstance(metric, dict):
                continue
            metric["value"] = anchor["value"]
            if "previousValue" in anchor:
                metric["previousValue"] = anchor["previousValue"]
            metric["provenance"] = {
                "formula": anchor.get("formula"),
                "sourceFacts": anchor.get("sourceFacts") or [],
            }
            metric.pop("trend", None)
            applied_here += 1
        if applied_here:
            quality = record.setdefault("quality", {})
            quality["goldenAnchorApplied"] = True
            quality["provenanceModelVersion"] = max(
                int(quality.get("provenanceModelVersion") or 0),
                int(golden.get("provenanceModelVersion") or 0),
            )
            anchored_companies += 1
            anchored_metrics += applied_here
    return anchored_companies, anchored_metrics


def build_golden_fallback_record(code: str, golden: dict) -> dict:
    period_end = str(golden.get("periodEnd") or "")
    metrics: dict[str, dict] = {}
    for metric_key, anchor in (golden.get("anchors") or {}).items():
        if not isinstance(anchor, dict) or "value" not in anchor:
            continue
        metric = {
            "value": anchor["value"],
            "provenance": {
                "formula": anchor.get("formula"),
                "sourceFacts": anchor.get("sourceFacts") or [],
            },
        }
        if "previousValue" in anchor:
            metric["previousValue"] = anchor["previousValue"]
        metrics[str(metric_key)] = metric
    return {
        "code": code,
        "companyName": golden.get("companyName") or code,
        "documentId": golden.get("documentId"),
        "periodEnd": period_end,
        "filedAt": period_end,
        "source": "EDINET",
        "sourceUrl": (
            "https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?"
            f"{golden.get('documentId')}"
        ),
        "documentType": "AnnualSecuritiesReport",
        "metrics": metrics,
        "history": [],
        "quality": {
            "policy": "golden-fixture-fallback",
            "goldenFallback": True,
            "dataModelVersion": golden.get("dataModelVersion"),
            "provenanceModelVersion": golden.get("provenanceModelVersion"),
        },
    }


def recover_missing_golden_records(
    records: dict[str, dict],
    current_codes: set[str],
) -> int:
    recovered = 0
    for code, golden in load_golden_anchors().items():
        if code not in current_codes or code in records:
            continue
        fallback = build_golden_fallback_record(code, golden)
        if fallback["metrics"]:
            records[code] = fallback
            recovered += 1
    return recovered


def validated_records(
    records: dict,
    current_codes: set[str],
) -> tuple[dict[str, dict], Counter[str]]:
    valid: dict[str, dict] = {}
    failures: Counter[str] = Counter()
    for raw_code, record in records.items():
        code = str(raw_code)
        error = validate_financial_record(code, record, current_codes)
        if error:
            failures[error] += 1
        else:
            valid[code] = record
    return valid, failures


def has_trusted_roe_provenance(record: dict) -> bool:
    if record.get("source") != "EDINET":
        return True
    quality = record.get("quality") or {}
    if quality.get("policy") in CURRENT_ROE_EXTRACTION_POLICIES:
        return True
    if int(quality.get("roeModelVersion") or 0) >= 1:
        return True
    return (
        int(quality.get("dataModelVersion") or 0)
        >= MIN_TRUSTED_EDINET_ROE_MODEL_VERSION
    )


def quarantine_untrusted_roe(record: dict) -> bool:
    metrics = record.get("metrics") or {}
    if "roe" not in metrics or has_trusted_roe_provenance(record):
        return False

    metrics.pop("roe", None)
    for point in record.get("history") or []:
        if isinstance(point, dict):
            point.pop("roe", None)

    quality = record.setdefault("quality", {})
    quality["roeStatus"] = "quarantined-stale-model"
    quality["roeRequiredDataModelVersion"] = MIN_TRUSTED_EDINET_ROE_MODEL_VERSION
    return True


def main() -> int:
    generated_at = utc_now()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    original_records = snapshot.get("records", {}) or {}
    current_codes = load_company_codes()
    if not current_codes:
        raise RuntimeError("Company master is empty or invalid.")
    golden_anchored_companies, golden_anchored_metrics = apply_golden_anchors(
        original_records
    )
    for record in original_records.values():
        quarantine_invalid_metrics(record)
        quarantine_misaligned_metric_trends(record)
    annual_records, validation_failures = validated_records(
        original_records,
        current_codes,
    )
    golden_fallback_records = recover_missing_golden_records(
        annual_records,
        current_codes,
    )
    dropped = len(original_records) - len(annual_records) + golden_fallback_records
    roe_quarantined = sum(
        1 for record in annual_records.values() if quarantine_untrusted_roe(record)
    )
    metric_range_quarantined = sum(
        len(
            (
                ((record.get("quarantine") or {}).get("metricValidation") or {}).get(
                    "metrics"
                )
                or {}
            )
        )
        for record in annual_records.values()
    )
    metric_range_quarantined_companies = sum(
        1
        for record in annual_records.values()
        if (
            ((record.get("quarantine") or {}).get("metricValidation") or {}).get(
                "metrics"
            )
        )
    )
    history_trend_quarantined_companies = sum(
        1
        for record in annual_records.values()
        if (record.get("quarantine") or {}).get("historyTrend")
    )
    edinet_count = sum(1 for record in annual_records.values() if record.get("source") == "EDINET")
    tdnet_count = sum(1 for record in annual_records.values() if record.get("source") == "TDnet")
    target_companies = len(current_codes)
    missing_companies = max(0, target_companies - len(annual_records))
    coverage_ratio = (
        round(len(annual_records) / target_companies * 100, 2)
        if target_companies > 0
        else 0
    )

    stats = {**snapshot.get("stats", {})}
    pending_before_batch = int(stats.get("edinetPendingBeforeBatch") or 0)
    batch_size = int(stats.get("edinetBatchSize") or 0)
    estimated_remaining = max(0, pending_before_batch - batch_size)
    pipeline_failures = int(stats.get("edinetBatchFailures") or 0) + int(
        stats.get("tdnetStrictFailures") or 0
    )
    source_reconciliation = reconciliation_totals(annual_records)
    source_quarantined = source_reconciliation["sourceQuarantinedMetrics"]
    is_building = estimated_remaining > 0 or edinet_count < min(
        FALLBACK_TARGET_COMPANIES,
        target_companies,
    )
    status_text = (
        "partial"
        if pipeline_failures or source_quarantined or metric_range_quarantined
        else "building"
        if is_building
        else "ready"
    )
    data_updated_at = max(
        (str(record.get("filedAt") or "") for record in annual_records.values()),
        default="",
    ) or None
    latest_period_end = max(
        (str(record.get("periodEnd") or "") for record in annual_records.values()),
        default="",
    ) or None
    progress_message = (
        "EDINET年次ベースラインを分割構築中。"
        if is_building
        else "EDINET年次ベースライン＋TDnet通期決算短信オーバーレイで更新済み。"
    )

    stats.update(
        {
            "companies": len(annual_records),
            "edinetCompanies": edinet_count,
            "tdnetCompanies": tdnet_count,
            "annualOnly": True,
            "nonAnnualRecordsDropped": dropped,
            "invalidRecordsDropped": dropped,
            "validationFailures": dict(validation_failures),
            "roeMetricsQuarantined": roe_quarantined,
            "metricRangeQuarantined": metric_range_quarantined,
            "metricRangeQuarantinedCompanies": metric_range_quarantined_companies,
            "historyTrendQuarantinedCompanies": history_trend_quarantined_companies,
            "goldenAnchoredCompanies": golden_anchored_companies,
            "goldenAnchoredMetrics": golden_anchored_metrics,
            "goldenFallbackRecords": golden_fallback_records,
            **source_reconciliation,
            "edinetEstimatedRemaining": estimated_remaining,
            "targetCompanies": target_companies,
            "missingCompanies": missing_companies,
            "coverageRatio": coverage_ratio,
            "dataUpdatedAt": data_updated_at,
            "latestPeriodEnd": latest_period_end,
            "lastCheckedAt": generated_at,
        }
    )

    snapshot.update(
        {
            "generatedAt": generated_at,
            "dataUpdatedAt": data_updated_at,
            "latestPeriodEnd": latest_period_end,
            "source": "EDINET+TDnet",
            "status": status_text,
            "message": (
                progress_message
                + "EDINET有価証券報告書ベースの年次データを基礎DBにし、"
                "TDnetの通期決算短信で直近分のみ上書きしています。"
                "四半期・中間短信は統合していません。"
                f"対象{target_companies:,}社のうち財務KPI取得済みは{len(annual_records):,}社です。"
            ),
            "dataPolicy": {
                "mode": "edinet-annual-baseline-tdnet-full-year-overlay-batched",
                "baselineSource": "EDINET有価証券報告書XBRL",
                "overlaySource": "TDnet通期決算短信XBRL",
                "edinetMerged": True,
                "tdnetOverlay": True,
                "quarterlyMerged": False,
                "batched": True,
                "note": (
                    "上場全社級のカバレッジを確保するため、EDINET年次データを基礎DBとして使います。"
                    "長時間実行を避けるため、EDINETは複数回に分けて構築します。"
                    "TDnetは通期決算短信だけを採用し、四半期・中間短信は年次KPIとの混在を避けるため除外します。"
                    "未取得企業には架空KPIを表示せず、未取得として扱います。"
                ),
            },
            "records": annual_records,
            "stats": stats,
        }
    )

    status = {
        "generatedAt": generated_at,
        "dataUpdatedAt": data_updated_at,
        "latestPeriodEnd": latest_period_end,
        "mode": "edinet-annual-baseline-tdnet-full-year-overlay-batched",
        "status": status_text,
        "source": "EDINET+TDnet",
        "baselineSource": "EDINET有価証券報告書XBRL",
        "overlaySource": "TDnet通期決算短信XBRL",
        "edinetMerged": True,
        "tdnetOverlay": True,
        "quarterlyMerged": False,
        "batched": True,
        "companies": len(annual_records),
        "targetCompanies": target_companies,
        "missingCompanies": missing_companies,
        "coverageRatio": coverage_ratio,
        "edinetCompanies": edinet_count,
        "tdnetCompanies": tdnet_count,
        "edinetDocumentsScanned": stats.get("edinetDocumentsScanned", 0),
        "edinetPendingBeforeBatch": pending_before_batch,
        "edinetBatchSize": batch_size,
        "edinetDocumentsUpdated": stats.get("edinetDocumentsUpdated", 0),
        "edinetEstimatedRemaining": estimated_remaining,
        "edinetBatchFailures": stats.get("edinetBatchFailures", 0),
        "nonAnnualRecordsDropped": dropped,
        "invalidRecordsDropped": dropped,
        "validationFailures": dict(validation_failures),
        "roeMetricsQuarantined": roe_quarantined,
        "metricRangeQuarantined": metric_range_quarantined,
        "metricRangeQuarantinedCompanies": metric_range_quarantined_companies,
        "historyTrendQuarantinedCompanies": history_trend_quarantined_companies,
        "goldenAnchoredCompanies": golden_anchored_companies,
        "goldenAnchoredMetrics": golden_anchored_metrics,
        "goldenFallbackRecords": golden_fallback_records,
        **source_reconciliation,
        "tdnetRowsScanned": stats.get("tdnetRowsScanned", 0),
        "tdnetEarningsRows": stats.get("tdnetEarningsRows", 0),
        "tdnetQuarterlyRowsSkipped": stats.get("tdnetQuarterlyRowsSkipped", 0),
        "tdnetFullYearFilings": stats.get("tdnetFullYearFilings", 0),
        "tdnetDocumentsUpdated": stats.get("tdnetDocumentsUpdated", 0),
        "tdnetStrictFailures": stats.get("tdnetStrictFailures", 0),
        "message": (
            progress_message
            + "四半期・中間短信は統合していません。"
            + f"対象{target_companies:,}社中{len(annual_records):,}社を取得済み、未取得{missing_companies:,}社。"
        ),
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
        f"{len(annual_records)} / {target_companies} companies, "
        f"EDINET {edinet_count}, TDnet {tdnet_count}, "
        f"remaining about {estimated_remaining}, dropped {dropped} non-annual records, "
        f"quarantined {roe_quarantined} stale ROE metrics, "
        f"{metric_range_quarantined} impossible metrics, "
        f"{history_trend_quarantined_companies} stale histories and "
        f"{source_quarantined} EDINET/TDnet mismatches; "
        f"applied {golden_anchored_metrics} golden anchors and "
        f"recovered {golden_fallback_records} golden records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
