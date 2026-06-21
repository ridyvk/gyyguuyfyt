#!/usr/bin/env python3
"""Shared validation and XBRL context selection for financial snapshots."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECURITY_CODE = re.compile(r"^[0-9A-Z]{4}$")

ALLOWED_TOTAL_DIMENSION_MEMBERS = (
    "ConsolidatedMember",
    "NonConsolidatedMember",
    "ResultMember",
    "ActualMember",
)
REJECTED_CONTEXT_TOKENS = (
    "ForecastMember",
    "UpperMember",
    "LowerMember",
    "NextYear",
)


def is_iso_date(value: object) -> bool:
    text = str(value or "")
    if not ISO_DATE.fullmatch(text):
        return False
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def normalize_security_code(value: object) -> str | None:
    raw = str(value or "").strip().upper()
    code = raw[:4]
    return code if SECURITY_CODE.fullmatch(code) else None


def filing_order_key(filing: dict) -> tuple[str, str, str]:
    period_end = str(filing.get("periodEnd") or "")
    if not is_iso_date(period_end):
        period_end = ""
    return (
        period_end,
        str(filing.get("submitDateTime") or filing.get("filedAt") or ""),
        str(filing.get("docID") or filing.get("documentId") or ""),
    )


def record_order_key(record: dict | None) -> tuple[str, str, str]:
    if not isinstance(record, dict):
        return ("", "", "")
    return filing_order_key(record)


def dimension_value(element: object, member: str) -> str:
    attributes = getattr(element, "attrib", {}) or {}
    dimension = str(attributes.get("dimension") or "")
    return f"{dimension}={member}" if dimension else member


def dimension_has_member(dimensions: list[str], member: str) -> bool:
    return any(
        dimension == member or dimension.endswith(f"={member}")
        for dimension in dimensions
    )


def is_total_actual_context(context_id: str, context: dict) -> bool:
    dimensions = [str(value) for value in context.get("dimensions", [])]
    text = context_id + " " + " ".join(dimensions)
    if any(token in text for token in REJECTED_CONTEXT_TOKENS):
        return False
    return all(
        any(
            dimension == member or dimension.endswith(f"={member}")
            for member in ALLOWED_TOTAL_DIMENSION_MEMBERS
        )
        for dimension in dimensions
    )


def context_days(context: dict) -> int | None:
    try:
        return (
            date.fromisoformat(str(context["end"]))
            - date.fromisoformat(str(context["start"]))
        ).days
    except (KeyError, TypeError, ValueError):
        return None


def context_rank(
    context_id: str,
    context: dict,
    period_end: str,
    duration: bool,
) -> tuple[int, int, int, int, int, int, int]:
    dimensions = [str(value) for value in context.get("dimensions", [])]
    actual_end = context.get("end") if duration else context.get("instant")
    days = context_days(context) or 0
    return (
        1 if actual_end == period_end else 0,
        1 if not dimensions else 0,
        1 if dimension_has_member(dimensions, "ConsolidatedMember") else 0,
        0 if dimension_has_member(dimensions, "NonConsolidatedMember") else 1,
        1 if dimension_has_member(dimensions, "ResultMember") or dimension_has_member(dimensions, "ActualMember") else 0,
        1 if "CurrentYear" in context_id else 0,
        -abs(days - 365) if duration else 0,
    )


def consolidation_scope(context_id: str, context: dict) -> str:
    dimensions = [str(value) for value in context.get("dimensions", [])]
    text = context_id + " " + " ".join(dimensions)
    if dimension_has_member(dimensions, "NonConsolidatedMember") or "NonConsolidated" in context_id:
        return "non-consolidated"
    if dimension_has_member(dimensions, "ConsolidatedMember") or "Consolidated" in text or is_total_actual_context(context_id, context):
        return "consolidated"
    return "unknown"


def select_preferred_facts(
    contexts: dict,
    facts: dict,
    names: tuple[str, ...],
    duration: bool,
    duration_range: tuple[int, int] = (250, 460),
) -> dict[str, dict]:
    """Select facts while retaining the XBRL fields needed for an audit trail."""
    result: dict[str, dict] = {}
    for name in names:
        grouped: dict[str, list[tuple[str, float, dict]]] = defaultdict(list)
        for entry in facts.get(name, []):
            context_id, value = entry[0], entry[1]
            detail = entry[2] if len(entry) > 2 and isinstance(entry[2], dict) else {}
            context = contexts.get(context_id)
            if not context or not is_total_actual_context(context_id, context):
                continue
            period_end = context.get("end") if duration else context.get("instant")
            if not is_iso_date(period_end):
                continue
            if duration:
                days = context_days(context)
                if days is None or not duration_range[0] <= days <= duration_range[1]:
                    continue
            grouped[str(period_end)].append((context_id, value, detail))

        for period_end, candidates in grouped.items():
            if period_end in result:
                continue
            context_id, value, detail = max(
                candidates,
                key=lambda candidate: context_rank(
                    candidate[0], contexts[candidate[0]], period_end, duration
                ),
            )
            context = contexts[context_id]
            selected = {
                "concept": name,
                "tag": str(detail.get("tag") or name),
                "contextRef": context_id,
                "periodStart": context.get("start"),
                "periodEnd": period_end,
                "periodType": "duration" if duration else "instant",
                "unitRef": detail.get("unitRef"),
                "consolidation": consolidation_scope(context_id, context),
                "dimensions": list(context.get("dimensions", [])),
                "rawValue": value,
            }
            namespace = detail.get("namespace")
            if namespace:
                selected["namespace"] = namespace
            scale = detail.get("scale")
            if scale is not None:
                selected["scale"] = scale
            result[period_end] = {
                key: item for key, item in selected.items() if item is not None
            }
    return result


def select_preferred_values(
    contexts: dict,
    facts: dict,
    names: tuple[str, ...],
    duration: bool,
    duration_range: tuple[int, int] = (250, 460),
) -> dict[str, float]:
    """Select total actual facts, preserving concept priority in ``names``."""
    return {
        period_end: fact["rawValue"]
        for period_end, fact in select_preferred_facts(
            contexts,
            facts,
            names,
            duration,
            duration_range,
        ).items()
    }


def provenance_inputs(
    selected: dict[str, dict[str, list[dict]]],
    series_names: tuple[str, ...],
    period_end: str,
    include_previous: bool = False,
) -> list[dict]:
    inputs: list[dict] = []
    for series_name in series_names:
        periods = selected.get(series_name, {})
        selected_periods: list[tuple[str, str]] = [("current", period_end)]
        if include_previous:
            previous_period = max(
                (candidate for candidate in periods if candidate < period_end),
                default=None,
            )
            if previous_period:
                selected_periods.append(("previous", previous_period))
        for period_role, selected_period in selected_periods:
            for fact in periods.get(selected_period, []):
                inputs.append(
                    {
                        **fact,
                        "role": f"{series_name}.{period_role}",
                    }
                )
    return inputs


def attach_metric_provenance(
    metrics: dict,
    key: str,
    formula: str,
    source_facts: list[dict],
) -> None:
    metric = metrics.get(key)
    if not isinstance(metric, dict):
        return
    metric["provenance"] = {
        "formula": formula,
        "sourceFacts": source_facts,
    }



HARD_METRIC_RANGES: dict[str, tuple[float | None, float | None]] = {
    "revenueGrowth": (-100.0, None),
    "equityRatio": (None, 100.0),
    "debtRatio": (0.0, None),
    "inventoryGrowth": (-100.0, None),
    "receivablesGrowth": (-100.0, None),
}


def metric_range_error(metric_key: str, metric: object) -> str | None:
    """Return a hard-range violation for one metric, including comparisons."""
    if not isinstance(metric, dict):
        return None
    bounds = HARD_METRIC_RANGES.get(metric_key)
    if bounds is None:
        return None
    minimum, maximum = bounds
    candidates: list[tuple[str, object]] = [
        ("value", metric.get("value")),
        ("previousValue", metric.get("previousValue")),
    ]
    trend = metric.get("trend")
    if isinstance(trend, list):
        candidates.extend((f"trend[{index}]", value) for index, value in enumerate(trend))
    for field, value in candidates:
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if not math.isfinite(numeric):
            continue
        if minimum is not None and numeric < minimum:
            return f"{field}-below-minimum-{minimum:g}"
        if maximum is not None and numeric > maximum:
            return f"{field}-above-maximum-{maximum:g}"
    return None



def remove_history_metric(record: dict, metric_key: str) -> None:
    for point in record.get("history") or []:
        if isinstance(point, dict):
            point.pop(metric_key, None)


def quarantine_invalid_metrics(record: object) -> int:
    """Remove impossible KPIs while preserving the rest of the company record."""
    if not isinstance(record, dict):
        return 0
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    quarantined: dict[str, dict] = {}
    for metric_key, metric in list(metrics.items()):
        reason = metric_range_error(metric_key, metric)
        if reason is None:
            continue
        quarantined[metric_key] = {
            "reason": reason,
            "metric": metric,
        }
        metrics.pop(metric_key, None)
        remove_history_metric(record, metric_key)
    if not quarantined:
        return 0

    quarantine = record.setdefault("quarantine", {})
    metric_validation = quarantine.setdefault(
        "metricValidation",
        {"policy": "hard-accounting-ranges-v1", "metrics": {}},
    )
    metric_validation.setdefault("metrics", {}).update(quarantined)
    quality = record.setdefault("quality", {})
    quality["metricValidationModelVersion"] = 1
    quality["metricValidationStatus"] = "quarantined"
    return len(quarantined)


def quarantine_misaligned_metric_trends(record: object) -> int:
    """Drop chart trends when their latest year is not the record's fiscal year."""
    if not isinstance(record, dict):
        return 0
    history = record.get("history")
    metrics = record.get("metrics")
    period_end = str(record.get("periodEnd") or "")
    if not isinstance(history, list) or not history or not isinstance(metrics, dict):
        return 0
    latest = history[-1] if isinstance(history[-1], dict) else {}
    latest_year = str(latest.get("year") or "")
    expected_year = period_end[:7].replace("-", "/")
    if latest_year == expected_year:
        return 0

    removed: list[str] = []
    for metric_key, metric in metrics.items():
        if isinstance(metric, dict) and "trend" in metric:
            metric.pop("trend", None)
            removed.append(metric_key)
    if not removed:
        return 0

    quarantine = record.setdefault("quarantine", {})
    quarantine["historyTrend"] = {
        "reason": "latest-history-period-does-not-match-record-period",
        "expectedYear": expected_year,
        "latestHistoryYear": latest_year,
        "metrics": sorted(removed),
    }
    quality = record.setdefault("quality", {})
    quality["historyTrendValidationModelVersion"] = 1
    quality["historyTrendStatus"] = "quarantined"
    return len(removed)


def is_unusable_record_validation(error: object) -> bool:
    """Return whether a structurally valid filing yielded no supported KPI facts."""
    message = str(error or "")
    return message == "missing-metrics" or message.startswith("no metrics extracted:")


def validate_financial_record(
    code: str,
    record: object,
    current_codes: set[str],
) -> str | None:
    if code not in current_codes:
        return "not-in-company-master"
    if not isinstance(record, dict):
        return "not-an-object"
    if str(record.get("code") or "") != code:
        return "code-mismatch"
    if not is_iso_date(record.get("periodEnd")):
        return "invalid-period-end"
    filed_at = str(record.get("filedAt") or "")
    if not is_iso_date(filed_at[:10]):
        return "invalid-filed-at"
    source = record.get("source")
    if source == "TDnet" and record.get("documentType") != "FullYearEarnings":
        return "non-annual-tdnet"
    if source not in {"EDINET", "TDnet"}:
        return "unsupported-source"
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        return "missing-metrics"
    if not metrics:
        quarantine = record.get("quarantine") or {}
        source_quarantine = quarantine.get("sourceReconciliation") or {}
        disputed_metrics = source_quarantine.get("metrics") or {}
        if not isinstance(disputed_metrics, dict) or not disputed_metrics:
            return "missing-metrics"
    for metric_key, metric in metrics.items():
        value = metric.get("value") if isinstance(metric, dict) else None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            return "invalid-metric"
        range_error = metric_range_error(metric_key, metric)
        if range_error:
            return f"invalid-metric-range:{metric_key}:{range_error}"
    return None
