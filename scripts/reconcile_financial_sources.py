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


def metric_basis(metric_key: str, metric: dict) -> str:
    facts = source_facts(metric)
    roles = {str(fact.get("role") or "") for fact in facts}
    if metric_key == "roe":
        return "disclosed" if "disclosedRoe.current" in roles else "calculated"
    if metric_key == "equityRatio":
        return (
            "disclosed"
            if "disclosedEquityRatio.current" in roles
            else "calculated"
        )
    if metric_key == "netCash":
        cash = next(
            (
                str(fact.get("concept") or fact.get("tag") or "")
                for fact in facts
                if fact.get("role") == "cash.current"
            ),
            "unknown",
        )
        return f"cash:{cash.rsplit(':', 1)[-1]}"
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
    if metric_key not in {"roe", "equityRatio", "netCash"}:
        return True
    return metric_basis(metric_key, edinet_metric) == metric_basis(
        metric_key, tdnet_metric
    )


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
    if selected_source == "TDnet":
        copy_tdnet_history_metric(record, tdnet_record, metric_key)


def strip_previous_comparison(record: dict, metric_key: str) -> None:
    metric = (record.get("metrics") or {}).get(metric_key)
    if isinstance(metric, dict):
        metric.pop("previousValue", None)
        metric.pop("trend", None)
    remove_history_metric(record, metric_key)


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
        }
    else:
        quarantine.pop("sourceReconciliation", None)
        if not quarantine:
            edinet_record.pop("quarantine", None)

    quality = edinet_record.setdefault("quality", {})
    quality["reconciliationModelVersion"] = RECONCILIATION_MODEL_VERSION
    quality["reconciliationStatus"] = status
    quality["reconciliationDocumentId"] = tdnet_record.get("documentId")
    quality["reconciliationSourceUrl"] = tdnet_record.get("sourceUrl")
    if "roe" in edinet_metrics and metric_results.get("roe", {}).get(
        "selectedSource"
    ) == "TDnet":
        quality["roeSource"] = "TDnet通期決算短信XBRL"
        quality["roeSourceUrl"] = tdnet_record.get("sourceUrl")
        quality["roeDocumentId"] = tdnet_record.get("documentId")

    return ReconciliationSummary(
        compared=matched + quarantined,
        matched=matched,
        quarantined=quarantined,
        edinet_only=edinet_only,
        tdnet_only=tdnet_only,
    )


def repair_stored_definition_quarantines(record: dict) -> int:
    """Restore v1 disputes that compared different definitions or only old periods."""
    quarantine = record.get("quarantine") or {}
    source_quarantine = quarantine.get("sourceReconciliation") or {}
    disputes = source_quarantine.get("metrics") or {}
    if not isinstance(disputes, dict) or not disputes:
        return 0

    reconciliation = record.setdefault("reconciliation", {})
    metric_results = reconciliation.setdefault("metrics", {})
    restored = 0
    for metric_key, dispute in list(disputes.items()):
        if not isinstance(dispute, dict):
            continue
        edinet_metric = dispute.get("edinet")
        tdnet_metric = dispute.get("tdnet")
        if not isinstance(edinet_metric, dict) or not isinstance(tdnet_metric, dict):
            continue

        selected_source = preferred_source(metric_key, edinet_metric, tdnet_metric)
        selected_metric = edinet_metric if selected_source == "EDINET" else tdnet_metric
        if not definitions_are_comparable(metric_key, edinet_metric, tdnet_metric):
            record.setdefault("metrics", {})[metric_key] = deepcopy(selected_metric)
            metric_results[metric_key] = {
                "status": "definition-difference",
                "selectedSource": selected_source,
                "basis": {
                    "EDINET": metric_basis(metric_key, edinet_metric),
                    "TDnet": metric_basis(metric_key, tdnet_metric),
                },
            }
        else:
            result = compare_metric(metric_key, edinet_metric, tdnet_metric)
            value_result = result["fields"].get("value")
            previous_result = result["fields"].get("previousValue")
            if not (
                value_result
                and value_result["matched"]
                and previous_result
                and not previous_result["matched"]
            ):
                continue
            record.setdefault("metrics", {})[metric_key] = deepcopy(selected_metric)
            strip_previous_comparison(record, metric_key)
            metric_results[metric_key] = {
                **result,
                "status": "matched-current-only",
                "selectedSource": selected_source,
                "excludedFields": ["previousValue", "trend"],
            }

        disputes.pop(metric_key)
        restored += 1

    remaining = sorted(disputes)
    reconciliation["modelVersion"] = RECONCILIATION_MODEL_VERSION
    reconciliation["status"] = "quarantined" if remaining else "matched"
    reconciliation["quarantinedMetrics"] = remaining
    quality = record.setdefault("quality", {})
    quality["reconciliationModelVersion"] = RECONCILIATION_MODEL_VERSION
    quality["reconciliationStatus"] = reconciliation["status"]
    if not remaining:
        quarantine.pop("sourceReconciliation", None)
        if not quarantine:
            record.pop("quarantine", None)
    return restored


def reconciliation_totals(records: dict[str, dict]) -> dict[str, int]:
    companies = matched = quarantined = 0
    for record in records.values():
        reconciliation = record.get("reconciliation")
        if not isinstance(reconciliation, dict):
            continue
        companies += 1
        for result in (reconciliation.get("metrics") or {}).values():
            status = result.get("status") if isinstance(result, dict) else None
            if status in {"matched", "definition-difference", "matched-current-only"}:
                matched += 1
            elif status == "quarantined":
                quarantined += 1
    return {
        "sourceReconciliationCompanies": companies,
        "sourceMatchedMetrics": matched,
        "sourceQuarantinedMetrics": quarantined,
    }
