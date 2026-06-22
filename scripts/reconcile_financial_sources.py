#!/usr/bin/env python3
"""Reconcile same-period EDINET and TDnet KPI records before publication."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

RECONCILIATION_MODEL_VERSION = 2

TOLERANCE_POLICY: dict[str, tuple[float, float]] = {
    "revenueGrowth": (1.0, 0.05),
    "operatingMargin": (0.5, 0.05),
    "netMargin": (0.5, 0.05),
    "roe": (0.75, 0.05),
    "equityRatio": (0.5, 0.02),
    "operatingCfMargin": (1.0, 0.10),
    "debtRatio": (0.05, 0.05),
    "netCash": (2.0, 0.02),
    "inventoryGrowth": (2.0, 0.10),
    "receivablesGrowth": (2.0, 0.10),
}
DEFAULT_TOLERANCE = (0.5, 0.05)


@dataclass(frozen=True)
class ReconciliationSummary:
    compared: int
    matched: int
    quarantined: int
    edinet_only: int
    tdnet_only: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def allowed_difference(metric_key: str, left: float, right: float) -> float:
    absolute, relative = TOLERANCE_POLICY.get(metric_key, DEFAULT_TOLERANCE)
    return max(absolute, max(abs(left), abs(right)) * relative)


def compare_metric(metric_key: str, edinet_metric: dict, tdnet_metric: dict) -> dict:
    fields: dict[str, dict] = {}
    mismatch = False
    for field in ("value", "previousValue"):
        edinet_value = numeric(edinet_metric.get(field))
        tdnet_value = numeric(tdnet_metric.get(field))
        if edinet_value is None or tdnet_value is None:
            continue
        difference = abs(edinet_value - tdnet_value)
        tolerance = allowed_difference(metric_key, edinet_value, tdnet_value)
        matched = difference <= tolerance
        mismatch = mismatch or not matched
        fields[field] = {
            "edinet": edinet_value,
            "tdnet": tdnet_value,
            "difference": round(difference, 4),
            "allowedDifference": round(tolerance, 4),
            "matched": matched,
        }

    return {
        "status": "mismatch" if mismatch else "matched",
        "fields": fields,
    }


def source_facts(metric: dict) -> list[dict]:
    provenance = metric.get("provenance") or {}
    facts = provenance.get("sourceFacts") or []
    return [fact for fact in facts if isinstance(fact, dict)]


METRIC_BASIS_ROLES: dict[str, tuple[str, ...]] = {
    "revenueGrowth": ("revenue.current", "revenue.previous"),
    "operatingMargin": ("operatingIncome.current", "revenue.current"),
    "netMargin": ("profit.current", "revenue.current"),
    "operatingCfMargin": ("operatingCf.current", "revenue.current"),
    "debtRatio": ("debt.current", "equity.current"),
    "netCash": ("cash.current", "debt.current"),
    "inventoryGrowth": ("inventory.current", "inventory.previous"),
    "receivablesGrowth": ("receivables.current", "receivables.previous"),
}


def fact_signature(metric: dict, roles: tuple[str, ...]) -> str:
    parts = []
    for fact in source_facts(metric):
        role = str(fact.get("role") or "")
        if role not in roles:
            continue
        concept = str(fact.get("concept") or fact.get("tag") or "unknown")
        parts.append(f"{role}={concept.rsplit(':', 1)[-1]}")
    return ",".join(sorted(parts)) or "unknown"


def metric_basis(metric_key: str, metric: dict) -> str:
    facts = source_facts(metric)
    roles = {str(fact.get("role") or "") for fact in facts}
    if metric_key == "roe":
        return (
            "disclosed"
            if "disclosedRoe.current" in roles
            else "calculated:"
            + fact_signature(
                metric,
                ("profit.current", "equity.current", "equity.previous"),
            )
        )
    if metric_key == "equityRatio":
        return (
            "disclosed"
            if "disclosedEquityRatio.current" in roles
            else "calculated:"
            + fact_signature(metric, ("equity.current", "assets.current"))
        )
    basis_roles = METRIC_BASIS_ROLES.get(metric_key)
    if basis_roles:
        return "facts:" + fact_signature(metric, basis_roles)
    return "same-definition"


def preferred_source(
    metric_key: str,
    edinet_metric: dict,
    tdnet_metric: dict,
) -> str:
    edinet_basis = metric_basis(metric_key, edinet_metric)
    tdnet_basis = metric_basis(metric_key, tdnet_metric)
    if metric_key in {"roe", "equityRatio"}:
        if tdnet_basis == "disclosed" and edinet_basis != "disclosed":
            return "TDnet"
        if edinet_basis == "disclosed":
            return "EDINET"
    return "EDINET"


def definitions_are_comparable(
    metric_key: str,
    edinet_metric: dict,
    tdnet_metric: dict,
) -> bool:
    if metric_key not in {"roe", "equityRatio", *METRIC_BASIS_ROLES}:
        return True
    return metric_basis(metric_key, edinet_metric) == metric_basis(
        metric_key, tdnet_metric
    )


def clear_metric_validation_quarantine(record: dict, metric_key: str) -> None:
    """Remove stale range-quarantine metadata after a valid metric is selected."""
    quarantine = record.get("quarantine")
    if not isinstance(quarantine, dict):
        return
    validation = quarantine.get("metricValidation")
    if not isinstance(validation, dict):
        return
    metrics = validation.get("metrics")
    if not isinstance(metrics, dict):
        return
    metrics.pop(metric_key, None)
    if not metrics:
        quarantine.pop("metricValidation", None)
    if not quarantine:
        record.pop("quarantine", None)


def select_metric(
    record: dict,
    tdnet_record: dict,
    metric_key: str,
    edinet_metric: dict,
    tdnet_metric: dict,
    selected_source: str,
) -> None:
    selected = edinet_metric if selected_source == "EDINET" else tdnet_metric
    record.setdefault("metrics", {})[metric_key] = deepcopy(selected)
    clear_metric_validation_quarantine(record, metric_key)
    if selected_source == "TDnet":
        copy_tdnet_history_metric(record, tdnet_record, metric_key)


def strip_previous_comparison(record: dict, metric_key: str) -> None:
    metric = (record.get("metrics") or {}).get(metric_key)
    if isinstance(metric, dict):
        metric.pop("previousValue", None)
        metric.pop("trend", None)
    remove_history_metric(record, metric_key)


GROWTH_METRICS = {"revenueGrowth", "inventoryGrowth", "receivablesGrowth"}


def fact_raw_value(metric: dict, role: str) -> float | None:
    values = [
        numeric(fact.get("rawValue"))
        for fact in source_facts(metric)
        if fact.get("role") == role
    ]
    finite = [value for value in values if value is not None]
    return sum(finite) if finite else None


def is_later_edinet_growth_revision(
    metric_key: str,
    edinet_metric: dict,
    tdnet_metric: dict,
    edinet_filed_at: object,
    tdnet_filed_at: object,
) -> bool:
    """Recognize a later annual filing that revises only the current raw fact."""
    if metric_key not in GROWTH_METRICS:
        return False
    if str(edinet_filed_at or "") <= str(tdnet_filed_at or ""):
        return False
    role_prefix = {
        "revenueGrowth": "revenue",
        "inventoryGrowth": "inventory",
        "receivablesGrowth": "receivables",
    }[metric_key]
    edinet_current = fact_raw_value(edinet_metric, f"{role_prefix}.current")
    tdnet_current = fact_raw_value(tdnet_metric, f"{role_prefix}.current")
    edinet_previous = fact_raw_value(edinet_metric, f"{role_prefix}.previous")
    tdnet_previous = fact_raw_value(tdnet_metric, f"{role_prefix}.previous")
    if None in {edinet_current, tdnet_current, edinet_previous, tdnet_previous}:
        return False
    previous_tolerance = max(1.0, max(abs(edinet_previous), abs(tdnet_previous)) * 1e-6)
    current_tolerance = max(1.0, max(abs(edinet_current), abs(tdnet_current)) * 1e-6)
    return (
        abs(edinet_previous - tdnet_previous) <= previous_tolerance
        and abs(edinet_current - tdnet_current) > current_tolerance
    )


def source_descriptor(record: dict) -> dict:
    return {
        "documentId": record.get("documentId"),
        "filedAt": record.get("filedAt"),
        "sourceUrl": record.get("sourceUrl"),
    }


def remove_history_metric(record: dict, metric_key: str) -> None:
    for point in record.get("history") or []:
        if isinstance(point, dict):
            point.pop(metric_key, None)


def copy_tdnet_history_metric(edinet_record: dict, tdnet_record: dict, metric_key: str) -> None:
    tdnet_values = {
        point.get("year"): point.get(metric_key)
        for point in tdnet_record.get("history") or []
        if isinstance(point, dict)
        and point.get("year")
        and numeric(point.get(metric_key)) is not None
    }
    for point in edinet_record.get("history") or []:
        if isinstance(point, dict) and point.get("year") in tdnet_values:
            point[metric_key] = tdnet_values[point["year"]]


def reconcile_same_period(
    edinet_record: dict,
    tdnet_record: dict,
    checked_at: str | None = None,
) -> ReconciliationSummary | None:
    """Mutate the EDINET record with matched supplements and isolated disputes."""
    if (
        edinet_record.get("source") != "EDINET"
        or tdnet_record.get("source") != "TDnet"
        or edinet_record.get("periodEnd") != tdnet_record.get("periodEnd")
    ):
        return None

    edinet_metrics = edinet_record.setdefault("metrics", {})
    tdnet_metrics = tdnet_record.get("metrics") or {}
    metric_results: dict[str, dict] = {}
    disputed: dict[str, dict] = {}
    matched = quarantined = edinet_only = tdnet_only = 0

    for metric_key in sorted(set(edinet_metrics) | set(tdnet_metrics)):
        edinet_metric = edinet_metrics.get(metric_key)
        tdnet_metric = tdnet_metrics.get(metric_key)
        if not isinstance(edinet_metric, dict):
            if isinstance(tdnet_metric, dict):
                edinet_metrics[metric_key] = deepcopy(tdnet_metric)
                clear_metric_validation_quarantine(edinet_record, metric_key)
                metric_results[metric_key] = {
                    "status": "tdnet-only",
                    "selectedSource": "TDnet",
                }
                tdnet_only += 1
            continue
        if not isinstance(tdnet_metric, dict):
            metric_results[metric_key] = {
                "status": "edinet-only",
                "selectedSource": "EDINET",
            }
            edinet_only += 1
            continue

        selected_source = preferred_source(metric_key, edinet_metric, tdnet_metric)
        edinet_basis = metric_basis(metric_key, edinet_metric)
        tdnet_basis = metric_basis(metric_key, tdnet_metric)
        if not definitions_are_comparable(metric_key, edinet_metric, tdnet_metric):
            select_metric(
                edinet_record,
                tdnet_record,
                metric_key,
                edinet_metric,
                tdnet_metric,
                selected_source,
            )
            metric_results[metric_key] = {
                "status": "definition-difference",
                "selectedSource": selected_source,
                "basis": {"EDINET": edinet_basis, "TDnet": tdnet_basis},
            }
            matched += 1
            continue

        result = compare_metric(metric_key, edinet_metric, tdnet_metric)
        if result["status"] == "mismatch":
            if is_later_edinet_growth_revision(
                metric_key,
                edinet_metric,
                tdnet_metric,
                edinet_record.get("filedAt"),
                tdnet_record.get("filedAt"),
            ):
                select_metric(
                    edinet_record,
                    tdnet_record,
                    metric_key,
                    edinet_metric,
                    tdnet_metric,
                    "EDINET",
                )
                metric_results[metric_key] = {
                    **result,
                    "status": "edinet-later-filing",
                    "selectedSource": "EDINET",
                    "reason": "later-edinet-annual-filing-revised-current-fact",
                }
                matched += 1
                continue
            value_result = result["fields"].get("value")
            previous_result = result["fields"].get("previousValue")
            if (
                value_result
                and value_result["matched"]
                and previous_result
                and not previous_result["matched"]
            ):
                select_metric(
                    edinet_record,
                    tdnet_record,
                    metric_key,
                    edinet_metric,
                    tdnet_metric,
                    selected_source,
                )
                strip_previous_comparison(edinet_record, metric_key)
                metric_results[metric_key] = {
                    **result,
                    "status": "matched-current-only",
                    "selectedSource": selected_source,
                    "excludedFields": ["previousValue", "trend"],
                }
                matched += 1
                continue
            absolute, relative = TOLERANCE_POLICY.get(
                metric_key,
                DEFAULT_TOLERANCE,
            )
            disputed[metric_key] = {
                "reason": "edinet-tdnet-value-mismatch",
                "tolerance": {
                    "absolute": absolute,
                    "relative": relative,
                },
                "comparison": result["fields"],
                "edinet": deepcopy(edinet_metric),
                "tdnet": deepcopy(tdnet_metric),
            }
            edinet_metrics.pop(metric_key, None)
            remove_history_metric(edinet_record, metric_key)
            metric_results[metric_key] = {
                **result,
                "status": "quarantined",
                "selectedSource": None,
            }
            quarantined += 1
            continue

        select_metric(
            edinet_record,
            tdnet_record,
            metric_key,
            edinet_metric,
            tdnet_metric,
            selected_source,
        )
        metric_results[metric_key] = {
            **result,
            "selectedSource": selected_source,
        }
        matched += 1

    checked = checked_at or utc_now()
    status = "quarantined" if disputed else "matched"
    edinet_record["reconciliation"] = {
        "modelVersion": RECONCILIATION_MODEL_VERSION,
        "checkedAt": checked,
        "periodEnd": edinet_record.get("periodEnd"),
        "status": status,
        "sources": {
            "EDINET": source_descriptor(edinet_record),
            "TDnet": source_descriptor(tdnet_record),
        },
        "metrics": metric_results,
        "quarantinedMetrics": sorted(disputed),
    }

    quarantine = edinet_record.setdefault("quarantine", {})
    if disputed:
        quarantine["sourceReconciliation"] = {
            "checkedAt": checked,
            "periodEnd": edinet_record.get("periodEnd"),
            "metrics": disputed,