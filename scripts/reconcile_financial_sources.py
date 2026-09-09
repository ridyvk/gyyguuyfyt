#!/usr/bin/env python3
"""Reconcile same-period EDINET and TDnet KPI records before publication."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

RECONCILIATION_MODEL_VERSION = 1

# Derived estimates can depend on a disputed input even when their own value
# was materialized before reconciliation. Keep them out of the public record.
SUPPLEMENTAL_KEYS = {"roa", "roic", "roicWaccSpread", "cashProfitGap", "wacc"}


def disputed_metrics(record: dict) -> dict:
    return ((record.get("quarantine") or {}).get("sourceReconciliation") or {}).get("metrics") or {}


def enforce_source_quarantine(record: dict) -> None:
    disputed = disputed_metrics(record)
    if not disputed:
        return
    for key in set(disputed) | SUPPLEMENTAL_KEYS:
        (record.get("metrics") or {}).pop(key, None)
        remove_history_metric(record, key)


def contained_source_quarantines(record: dict) -> set[str]:
    """Only count disputes with evidence and no exposed value as contained."""
    disputed = disputed_metrics(record)
    reconciliation = record.get("reconciliation") or {}
    if not disputed or reconciliation.get("periodEnd") != record.get("periodEnd"):
        return set()
    exposed = set(record.get("metrics") or {})
    for point in record.get("history") or []:
        exposed.update(point)
    if exposed & (set(disputed) | SUPPLEMENTAL_KEYS):
        return set()
    contained = set()
    for key, evidence in disputed.items():
        if (reconciliation.get("metrics") or {}).get(key, {}).get("status") != "quarantined":
            continue
        sources = evidence.get("sources") or reconciliation.get("sources") or {}
        if not all((sources.get(source) or {}).get("documentId") for source in ("EDINET", "TDnet")):
            continue
        comparison = evidence.get("comparison") or {}
        if any(
            field.get("matched") is False
            and numeric(field.get("edinet")) is not None
            and numeric(field.get("tdnet")) is not None
            and (evidence.get("edinet") or {}).get(name) == field["edinet"]
            and (evidence.get("tdnet") or {}).get(name) == field["tdnet"]
            for name, field in comparison.items()
        ):
            contained.add(key)
    return contained


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
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
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
    previous_disputes = deepcopy(disputed_metrics(edinet_record))
    previous_sources = deepcopy((edinet_record.get("reconciliation") or {}).get("sources") or {})
    metric_results: dict[str, dict] = {}
    disputed: dict[str, dict] = {}
    matched = quarantined = edinet_only = tdnet_only = 0

    for metric_key in sorted(set(edinet_metrics) | set(tdnet_metrics) | set(previous_disputes)):
        edinet_metric = edinet_metrics.get(metric_key)
        tdnet_metric = tdnet_metrics.get(metric_key)
        previous_dispute = previous_disputes.get(metric_key)
        if previous_dispute and not isinstance(edinet_metric, dict):
            # Repeated polling must compare with the isolated EDINET value,
            # rather than misclassify TDnet as the sole available source.
            edinet_metric = previous_dispute.get("edinet")
            if not isinstance(tdnet_metric, dict):
                disputed[metric_key] = previous_dispute
                disputed[metric_key].setdefault("sources", previous_sources)
                metric_results[metric_key] = {"status": "quarantined", "selectedSource": None}
                quarantined += 1
                continue
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

        result = compare_metric(metric_key, edinet_metric, tdnet_metric)
        if result["status"] == "mismatch":
            absolute, relative = TOLERANCE_POLICY.get(
                metric_key,
                DEFAULT_TOLERANCE,
            )
            disputed[metric_key] = {
                "reason": "edinet-tdnet-value-mismatch",
                "sources": {"EDINET": source_descriptor(edinet_record), "TDnet": source_descriptor(tdnet_record)},
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

        selected_source = "TDnet" if metric_key == "roe" else "EDINET"
        edinet_metrics[metric_key] = deepcopy(edinet_metric)
        if selected_source == "TDnet":
            edinet_metrics[metric_key] = deepcopy(tdnet_metric)
            copy_tdnet_history_metric(edinet_record, tdnet_record, metric_key)
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

    enforce_source_quarantine(edinet_record)

    return ReconciliationSummary(
        compared=matched + quarantined,
        matched=matched,
        quarantined=quarantined,
        edinet_only=edinet_only,
        tdnet_only=tdnet_only,
    )


def reconciliation_totals(records: dict[str, dict]) -> dict[str, int]:
    companies = matched = quarantined = 0
    for record in records.values():
        reconciliation = record.get("reconciliation")
        if not isinstance(reconciliation, dict):
            continue
        companies += 1
        for result in (reconciliation.get("metrics") or {}).values():
            status = result.get("status") if isinstance(result, dict) else None
            if status == "matched":
                matched += 1
            elif status == "quarantined":
                quarantined += 1
    return {
        "sourceReconciliationCompanies": companies,
        "sourceMatchedMetrics": matched,
        "sourceQuarantinedMetrics": quarantined,
    }
