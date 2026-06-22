#!/usr/bin/env python3
"""Finalize KPI Scope snapshot as EDINET annual baseline + TDnet annual overlay."""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from data_quality import (
    normalize_security_code,
    quarantine_invalid_metrics,
    quarantine_misaligned_metric_trends,
    validate_financial_record,
)
from reconcile_financial_sources import (
    reconciliation_dispute_details,
    reconciliation_totals,
    repair_stored_definition_quarantines,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/financials.json"
STATUS = ROOT / "public/data/update-status.json"
COMPANY_MASTER = ROOT / "src/data/listedCompanies.json"
VERIFIED_OVERRIDES = ROOT / "public/data/verified-financial-overrides.json"
FALLBACK_TARGET_COMPANIES = 3000
MIN_TRUSTED_EDINET_ROE_MODEL_VERSION = 6


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


def load_verified_overrides() -> dict:
    if not VERIFIED_OVERRIDES.exists():
        return {"schemaVersion": 1, "overrides": {}}
    payload = json.loads(VERIFIED_OVERRIDES.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1:
        raise ValueError("Unsupported verified financial override schema")
    if not isinstance(payload.get("overrides"), dict):
        raise ValueError("Verified financial overrides must be an object")
    return payload


def clear_metric_quarantine(record: dict, metric_key: str) -> None:
    quarantine = record.get("quarantine")
    if not isinstance(quarantine, dict):
        return
    validation = quarantine.get("metricValidation")
    metrics = validation.get("metrics") if isinstance(validation, dict) else None
    if isinstance(metrics, dict):
        metrics.pop(metric_key, None)
        if not metrics:
            quarantine.pop("metricValidation", None)
            quality = record.get("quality")
            if isinstance(quality, dict):
                quality.pop("metricValidationStatus", None)
    if not quarantine:
        record.pop("quarantine", None)


def apply_verified_metric_overrides(records: dict, payload: dict) -> int:
    applied = 0
    for raw_code, override in payload.get("overrides", {}).items():
        code = str(raw_code)
        if not isinstance(override, dict):
            raise ValueError(f"Invalid verified override for {code}")
        record = records.get(code)
        if not isinstance(record, dict):
            continue
        if record.get("periodEnd") != override.get("periodEnd"):
            continue
        metric_key = str(override.get("metricKey") or "")
        if metric_key != "equityRatio":
            raise ValueError(f"Unsupported verified metric override: {metric_key}")
        value = override.get("value")
        previous_value = override.get("previousValue")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value > 100
            or isinstance(previous_value, bool)
            or not isinstance(previous_value, (int, float))
            or not math.isfinite(previous_value)
            or previous_value > 100
        ):
            raise ValueError(f"Invalid verified equity ratio override for {code}")

        source_url = str(override.get("sourceUrl") or "")
        document_id = str(override.get("documentId") or "")
        if not source_url.startswith("https://www2.jpx.co.jp/disc/") or not document_id:
            raise ValueError(f"Untrusted verified override source for {code}")

        metric = {
            "value": round(float(value), 2),
            "previousValue": round(float(previous_value), 2),
            "provenance": {
                "formula": "official disclosed equity ratio",
                "sourceFacts": [
                    {
                        "role": "disclosedEquityRatio.current",
                        "concept": "EquityRatio",
                        "tag": "JPX-PDF:EquityRatio",
                        "contextRef": "official-earnings-summary-page-1",
                        "periodEnd": override["periodEnd"],
                        "periodType": "instant",
                        "unitRef": "%",
                        "consolidation": "consolidated",
                        "rawValue": value,
                    },
                    {
                        "role": "disclosedEquityRatio.previous",
                        "concept": "EquityRatio",
                        "tag": "JPX-PDF:EquityRatio",
                        "contextRef": "official-earnings-summary-page-1",
                        "periodEnd": override["previousPeriodEnd"],
                        "periodType": "instant",
                        "unitRef": "%",
                        "consolidation": "consolidated",
                        "rawValue": previous_value,
                    },
                ],
            },
        }
        record.setdefault("metrics", {})[metric_key] = metric
        clear_metric_quarantine(record, metric_key)
        quality = record.setdefault("quality", {})
        quality["verifiedOverrideModelVersion"] = 1
        quality.setdefault("verifiedOverrides", {})[metric_key] = {
            "documentId": document_id,
            "source": override.get("source"),
            "sourceUrl": source_url,
            "verifiedAt": override.get("verifiedAt"),
            "evidence": override.get("evidence"),
        }
        applied += 1
    return applied


def main() -> int:
    generated_at = utc_now()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    original_records = snapshot.get("records", {}) or {}
    current_codes = load_company_codes()
    if not current_codes:
        raise RuntimeError("Company master is empty or invalid.")
    verified_metric_overrides_applied = apply_verified_metric_overrides(
        original_records,
        load_verified_overrides(),
    )
    source_quarantines_repaired = sum(
        repair_stored_definition_quarantines(record)
        for record in original_records.values()
        if isinstance(record, dict)
    )
    for record in original_records.values():
        quarantine_invalid_metrics(record)
        quarantine_misaligned_metric_trends(record)
    annual_records, validation_failures = validated_records(
        original_records,
        current_codes,
    )
    dropped = len(original_records) - len(annual_records)
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
    source_reconciliation_details = reconciliation_dispute_details(annual_records)
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
            "sourceDefinitionQuarantinesRepaired": source_quarantines_repaired,
            "verifiedMetricOverridesApplied": verified_metric_overrides_applied,
            **source_reconciliation,
            "sourceReconciliationDisputes": source_reconciliation_details,
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
        "verifiedMetricOverridesApplied": verified_metric_overrides_applied,
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
        f"{source_quarantined} EDINET/TDnet mismatches."
    )
    if source_reconciliation_details:
        print(
            "Source reconciliation disputes: "
            + json.dumps(source_reconciliation_details, ensure_ascii=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
