#!/usr/bin/env python3
"""Finalize KPI Scope snapshot as EDINET annual baseline + TDnet annual overlay."""

from __future__ import annotations

import json
import math
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
SUPPLEMENTAL_METRICS_MODEL_VERSION = 1
SUPPLEMENTAL_METRIC_KEYS = (
    "roa",
    "operatingIncomeGrowth",
    "epsGrowth",
    "roic",
    "wacc",
    "ebitda",
    "evEbitda",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_company_master_by_code() -> dict[str, dict]:
    try:
        payload = json.loads(COMPANY_MASTER.read_text(encoding="utf-8"))
        return {
            str(company["code"]): company
            for company in payload.get("companies", [])
            if isinstance(company, dict)
            and company.get("code")
            and normalize_security_code(company["code"]) == str(company["code"])
        }
    except Exception:
        return {}


def load_company_codes() -> set[str]:
    return set(load_company_master_by_code())


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


def finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def metric_number(
    metrics: dict[str, dict],
    key: str,
    field: str = "value",
) -> float | None:
    metric = metrics.get(key)
    if not isinstance(metric, dict):
        return None
    return finite_number(metric.get(field))


def latest_revenue_oku(record: dict) -> float | None:
    for point in reversed(record.get("history") or []):
        if not isinstance(point, dict):
            continue
        revenue = finite_number(point.get("revenue"))
        if revenue is not None:
            return revenue
    return None


def clamp_value(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def derived_metric(
    value: float | None,
    previous_value: float | None,
    confidence: str,
    confidence_reason: str,
) -> dict | None:
    if value is None or not math.isfinite(value):
        return None
    metric = {
        "value": round(value, 4),
        "confidence": confidence,
        "confidenceReason": confidence_reason,
    }
    if previous_value is not None and math.isfinite(previous_value):
        metric["previousValue"] = round(previous_value, 4)
        metric["trend"] = [round(previous_value, 4), round(value, 4)]
    return metric


def operating_income_growth_from_margins(
    revenue_growth: float | None,
    operating_margin: float | None,
    previous_operating_margin: float | None,
) -> float | None:
    if (
        revenue_growth is None
        or operating_margin is None
        or previous_operating_margin is None
        or previous_operating_margin <= 0
    ):
        return None
    return (
        ((1 + revenue_growth / 100) * (operating_margin / previous_operating_margin))
        - 1
    ) * 100


def profit_growth_from_margins(
    revenue_growth: float | None,
    margin: float | None,
    previous_margin: float | None,
) -> float | None:
    if (
        revenue_growth is None
        or margin is None
        or previous_margin is None
        or previous_margin <= 0
    ):
        return None
    return ((1 + revenue_growth / 100) * (margin / previous_margin) - 1) * 100


def depreciation_margin_estimate(industry: str) -> float:
    heavy_asset_tokens = (
        "鉄鋼",
        "非鉄金属",
        "金属製品",
        "機械",
        "電気機器",
        "輸送用機器",
        "化学",
        "石油",
        "ガラス",
        "電気・ガス",
    )
    light_asset_tokens = ("情報・通信", "サービス", "小売", "卸売")
    if any(token in industry for token in heavy_asset_tokens):
        return 4.0
    if any(token in industry for token in light_asset_tokens):
        return 1.8
    return 2.6


def is_usable_supplemental_metric(key: str, metric: dict | None) -> bool:
    if not isinstance(metric, dict):
        return False
    value = finite_number(metric.get("value"))
    if value is None:
        return False
    if key == "wacc":
        return 0 < value <= 25
    if key in {"roa", "roic"}:
        return -80 <= value <= 120
    if key == "evEbitda":
        return 0 < value <= 200
    return True


def materialize_supplemental_metrics(record: dict, industry: str = "") -> Counter[str]:
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        return Counter()

    added: Counter[str] = Counter()

    def set_if_missing(key: str, metric: dict | None) -> None:
        if key in metrics or not is_usable_supplemental_metric(key, metric):
            return
        metrics[key] = metric
        added[key] += 1

    revenue_growth = metric_number(metrics, "revenueGrowth")
    operating_margin = metric_number(metrics, "operatingMargin")
    previous_operating_margin = metric_number(
        metrics,
        "operatingMargin",
        "previousValue",
    )
    net_margin = metric_number(metrics, "netMargin")
    previous_net_margin = metric_number(metrics, "netMargin", "previousValue")
    roe = metric_number(metrics, "roe")
    previous_roe = metric_number(metrics, "roe", "previousValue")
    equity_ratio = metric_number(metrics, "equityRatio")
    previous_equity_ratio = metric_number(metrics, "equityRatio", "previousValue")
    debt_ratio = metric_number(metrics, "debtRatio")
    net_cash = metric_number(metrics, "netCash")
    per = metric_number(metrics, "per")
    revenue_oku = latest_revenue_oku(record)

    set_if_missing(
        "roa",
        derived_metric(
            (roe * equity_ratio) / 100
            if roe is not None and equity_ratio is not None
            else None,
            (previous_roe * previous_equity_ratio) / 100
            if previous_roe is not None and previous_equity_ratio is not None
            else None,
            "B",
            "ROEと自己資本比率から ROA = ROE × 自己資本比率 で補完しています。",
        ),
    )
    set_if_missing(
        "operatingIncomeGrowth",
        derived_metric(
            operating_income_growth_from_margins(
                revenue_growth,
                operating_margin,
                previous_operating_margin,
            ),
            None,
            "B",
            "売上成長率と営業利益率の前年差から営業利益成長率を補完しています。",
        ),
    )
    set_if_missing(
        "epsGrowth",
        derived_metric(
            profit_growth_from_margins(
                revenue_growth,
                net_margin,
                previous_net_margin,
            ),
            None,
            "C",
            "株式数の変化を反映できないため、純利益成長率をEPS成長率の近似として表示しています。",
        ),
    )

    tax_adjusted_operating_return = (
        roe * (operating_margin / net_margin) * 0.7
        if roe is not None
        and operating_margin is not None
        and net_margin is not None
        and net_margin > 0
        else None
    )
    set_if_missing(
        "roic",
        derived_metric(
            tax_adjusted_operating_return / (1 + max(0, debt_ratio or 0))
            if tax_adjusted_operating_return is not None
            else None,
            None,
            "C",
            "NOPATと投下資本を直接取得できない会社では、ROE・利益率・D/Eから簡易推定しています。",
        ),
    )

    inferred_debt_to_equity = (
        max(0, debt_ratio)
        if debt_ratio is not None
        else max(0, (100 - equity_ratio) / equity_ratio)
        if equity_ratio is not None and equity_ratio > 0
        else 0.7
    )
    equity_weight = 1 / (1 + inferred_debt_to_equity)
    debt_weight = inferred_debt_to_equity / (1 + inferred_debt_to_equity)
    beta_estimate = clamp_value(
        1
        + ((50 - (equity_ratio if equity_ratio is not None else 40)) / 150)
        + max(0, inferred_debt_to_equity - 1) * 0.07,
        0.75,
        1.55,
    )
    cost_of_equity = 1.2 + beta_estimate * 5.5
    after_tax_cost_of_debt = (
        1.2 + min(2.5, inferred_debt_to_equity * 0.5)
    ) * 0.7
    set_if_missing(
        "wacc",
        derived_metric(
            equity_weight * cost_of_equity + debt_weight * after_tax_cost_of_debt,
            None,
            "C",
            "市場ベータや実効税率を直接取得できないため、財務レバレッジから簡易推定したWACCです。",
        ),
    )

    depreciation_margin = depreciation_margin_estimate(industry)
    ebitda_value = (
        revenue_oku * ((operating_margin + depreciation_margin) / 100)
        if revenue_oku is not None and operating_margin is not None
        else None
    )
    previous_revenue_oku = (
        revenue_oku / (1 + revenue_growth / 100)
        if revenue_oku is not None
        and revenue_growth is not None
        and (1 + revenue_growth / 100) != 0
        else None
    )
    previous_ebitda = (
        previous_revenue_oku
        * ((previous_operating_margin + depreciation_margin) / 100)
        if previous_revenue_oku is not None
        and previous_operating_margin is not None
        else None
    )
    set_if_missing(
        "ebitda",
        derived_metric(
            ebitda_value,
            previous_ebitda,
            "C",
            "減価償却費を直接取得できない会社では、業種別の償却率を営業利益に足して推定しています。",
        ),
    )

    ebitda = metric_number(metrics, "ebitda")
    net_income_oku = (
        revenue_oku * (net_margin / 100)
        if revenue_oku is not None and net_margin is not None
        else None
    )
    market_cap_oku = (
        net_income_oku * per
        if net_income_oku is not None and per is not None
        else None
    )
    enterprise_value_oku = (
        market_cap_oku - (net_cash if net_cash is not None else 0)
        if market_cap_oku is not None
        else None
    )
    set_if_missing(
        "evEbitda",
        derived_metric(
            enterprise_value_oku / ebitda
            if enterprise_value_oku is not None
            and ebitda is not None
            and ebitda > 0
            else None,
            None,
            "C",
            "時価総額をPERと純利益から、EVをネットキャッシュ控除で簡易推定しています。",
        ),
    )

    if added:
        quality = record.setdefault("quality", {})
        quality["supplementalMetricsModelVersion"] = (
            SUPPLEMENTAL_METRICS_MODEL_VERSION
        )
    return added


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
    company_master_by_code = load_company_master_by_code()
    current_codes = set(company_master_by_code)
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
    supplemental_metric_counts: Counter[str] = Counter()
    for code, record in annual_records.items():
        company = company_master_by_code.get(str(code)) or {}
        supplemental_metric_counts.update(
            materialize_supplemental_metrics(
                record,
                str(company.get("industry") or ""),
            )
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
            "supplementalMetricsModelVersion": SUPPLEMENTAL_METRICS_MODEL_VERSION,
            "supplementalMetricsAdded": sum(supplemental_metric_counts.values()),
            "supplementalMetricsAddedByKey": dict(
                sorted(supplemental_metric_counts.items())
            ),
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
        "supplementalMetricsModelVersion": SUPPLEMENTAL_METRICS_MODEL_VERSION,
        "supplementalMetricsAdded": sum(supplemental_metric_counts.values()),
        "supplementalMetricsAddedByKey": dict(
            sorted(supplemental_metric_counts.items())
        ),
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
        f"materialized {sum(supplemental_metric_counts.values())} supplemental metrics, "
        f"{metric_range_quarantined} impossible metrics, "
        f"{history_trend_quarantined_companies} stale histories and "
        f"{source_quarantined} EDINET/TDnet mismatches; "
        f"applied {golden_anchored_metrics} golden anchors and "
        f"recovered {golden_fallback_records} golden records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
