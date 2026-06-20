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
    "ResultMember",
    "ActualMember",
)
REJECTED_CONTEXT_TOKENS = (
    "NonConsolidated",
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


def is_total_actual_context(context_id: str, context: dict) -> bool:
    dimensions = [str(value) for value in context.get("dimensions", [])]
    text = context_id + " " + " ".join(dimensions)
    if any(token in text for token in REJECTED_CONTEXT_TOKENS):
        return False
    return all(
        any(member in dimension for member in ALLOWED_TOTAL_DIMENSION_MEMBERS)
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
) -> tuple[int, int, int, int, int, int]:
    dimensions = [str(value) for value in context.get("dimensions", [])]
    text = context_id + " " + " ".join(dimensions)
    actual_end = context.get("end") if duration else context.get("instant")
    days = context_days(context) or 0
    return (
        1 if actual_end == period_end else 0,
        1 if not dimensions else 0,
        1 if "ConsolidatedMember" in text else 0,
        1 if "ResultMember" in text or "ActualMember" in text else 0,
        1 if "CurrentYear" in context_id else 0,
        -abs(days - 365) if duration else 0,
    )


def consolidation_scope(context_id: str, context: dict) -> str:
    dimensions = [str(value) for value in context.get("dimensions", [])]
    text = context_id + " " + " ".join(dimensions)
    if "NonConsolidated" in text:
        return "non-consolidated"
    if "Consolidated" in text or is_total_actual_context(context_id, context):
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
    for metric in metrics.values():
        value = metric.get("value") if isinstance(metric, dict) else None
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return "invalid-metric"
    return None
