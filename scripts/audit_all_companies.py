#!/usr/bin/env python3
"""Generate a nightly audit report for the complete JPX company universe."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANY_MASTER = ROOT / "src" / "data" / "listedCompanies.json"
FINANCIALS = ROOT / "public" / "data" / "financials.json"
MARKET = ROOT / "public" / "data" / "market.json"
DEFAULT_OUTPUT = ROOT / "public" / "data" / "all-company-audit.json"

SCHEMA_VERSION = 2
MIN_EDINET_DATA_MODEL = 9
STALE_PERIOD_DAYS = 800
PROVENANCE_FIELDS = ("tag", "contextRef", "unitRef", "consolidation")
RATE_TOLERANCE_POINTS = 0.25
PIPELINE_RATE_TOLERANCE_POINTS = 0.5
KPI_KEYS = (
    "operatingMargin",
    "netMargin",
    "roe",
    "roa",
    "roic",
    "equityRatio",
    "operatingCfMargin",
    "netCash",
    "wacc",
)
SUPPLEMENTAL_METRIC_KEYS = {
    "roa",
    "roic",
    "wacc",
}
MARKET_DERIVED_METRIC_KEYS = set()
FINANCIAL_INDUSTRY_POLICIES = {
    "銀行業": ("roe", "roa", "per", "pbr"),
    "証券、商品先物取引業": ("roe", "roa", "per", "pbr"),
    "保険業": ("roe", "roa", "per", "pbr"),
    "その他金融業": (
        "revenueGrowth",
        "epsGrowth",
        "netMargin",
        "roe",
        "roa",
        "per",
        "pbr",
    ),
}

FINANCIAL_INDUSTRY_POLICIES = {
    industry: tuple(key for key in keys if key in KPI_KEYS)
    for industry, keys in FINANCIAL_INDUSTRY_POLICIES.items()
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def finite_metrics(record: dict) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, metric in (record.get("metrics") or {}).items():
        value = metric.get("value") if isinstance(metric, dict) else None
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ):
            result[str(key)] = float(value)
    return result


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def applicable_kpis(industry: str) -> set[str]:
    return set(FINANCIAL_INDUSTRY_POLICIES.get(industry, KPI_KEYS))


def latest_revenue_oku(record: dict | None) -> float | None:
    if not isinstance(record, dict):
        return None
    for point in reversed(record.get("history") or []):
        if not isinstance(point, dict):
            continue
        revenue = number(point.get("revenue"))
        if revenue is not None:
            return revenue
    return None


def market_metric_available(
    key: str,
    code: str,
    record: dict | None,
    metrics: dict[str, float],
    market_snapshot: dict | None,
) -> tuple[bool, str | None]:
    if key not in MARKET_DERIVED_METRIC_KEYS:
        return False, None
    market = market_snapshot if isinstance(market_snapshot, dict) else {}
    quote = (market.get("quotes") or {}).get(code)
    fundamentals = (market.get("fundamentals") or {}).get(code)
    if not isinstance(fundamentals, dict) and isinstance(record, dict):
        fundamentals = record.get("valuation")
    if not isinstance(quote, dict):
        return False, "missing-market-quote"
    if quote.get("stale"):
        return False, "stale-market-quote"
    close = number(quote.get("close"))
    if close is None or close <= 0:
        return False, "invalid-market-quote"
    if not isinstance(fundamentals, dict):
        return False, "missing-valuation-input"

    eps = number(fundamentals.get("forecastEps")) or number(fundamentals.get("eps"))
    bps = number(fundamentals.get("bps"))
    if key == "per":
        return (eps is not None and eps > 0, "missing-eps")
    if key == "pbr":
        return (bps is not None and bps > 0, "missing-bps")

    per = metrics.get("per")
    if per is None and eps is not None and eps > 0:
        per = close / eps
    ebitda = metrics.get("ebitda")
    net_margin = metrics.get("netMargin")
    revenue_oku = latest_revenue_oku(record)
    available = (
        per is not None
        and per > 0
        and ebitda is not None
        and ebitda > 0
        and net_margin is not None
        and revenue_oku is not None
    )
    return available, "missing-ev-ebitda-input"


def missing_metric_reason(
    key: str,
    company_status: str,
    code: str,
    record: dict | None,
    metrics: dict[str, float],
    market_snapshot: dict | None,
) -> str:
    available_from_market, market_reason = market_metric_available(
        key,
        code,
        record,
        metrics,
        market_snapshot,
    )
    if available_from_market:
        return "available-from-market"
    if company_status == "missing":
        return "missing-financial-record"
    if market_reason:
        return market_reason
    if key in SUPPLEMENTAL_METRIC_KEYS:
        return "missing-supplemental-input"
    return "source-fact-unavailable"


def build_metric_coverage(
    audited: list[dict],
    records: dict,
    market_snapshot: dict | None,
) -> dict[str, dict]:
    coverage = {
        key: {
            "available": 0,
            "missing": 0,
            "notApplicable": 0,
            "availabilityRatio": 0.0,
            "missingReasons": Counter(),
            "kind": (
                "market-derived"
                if key in {"per", "pbr"}
                else "supplemental-or-market-derived"
                if key == "evEbitda"
                else "supplemental-derived"
                if key in SUPPLEMENTAL_METRIC_KEYS
                else "source-extracted"
            ),
        }
        for key in KPI_KEYS
    }

    for company in audited:
        code = str(company.get("code") or "")
        industry = str(company.get("industry") or "")
        record = records.get(code)
        metrics = finite_metrics(record) if isinstance(record, dict) else {}
        applicable = applicable_kpis(industry)
        for key in KPI_KEYS:
            item = coverage[key]
            if key not in applicable:
                item["notApplicable"] += 1
                continue
            if key in metrics:
                item["available"] += 1
                continue
            market_available, _ = market_metric_available(
                key,
                code,
                record,
                metrics,
                market_snapshot,
            )
            if market_available:
                item["available"] += 1
                continue
            item["missing"] += 1
            item["missingReasons"][
                missing_metric_reason(
                    key,
                    str(company.get("status") or ""),
                    code,
                    record,
                    metrics,
                    market_snapshot,
                )
            ] += 1

    normalized = {}
    for key, item in coverage.items():
        denominator = item["available"] + item["missing"]
        normalized[key] = {
            **item,
            "availabilityRatio": percentage(item["available"], denominator),
            "missingReasons": dict(sorted(item["missingReasons"].items())),
        }
    return normalized


def provenance_counts(record: dict) -> tuple[int, int]:
    complete = 0
    incomplete = 0
    for metric in (record.get("metrics") or {}).values():
        if not isinstance(metric, dict):
            continue
        provenance = metric.get("provenance")
        facts = (
            provenance.get("sourceFacts")
            if isinstance(provenance, dict)
            else None
        )
        if not isinstance(facts, list) or not facts:
            continue
        complete_facts = all(
            isinstance(fact, dict)
            and all(fact.get(field) not in (None, "") for field in PROVENANCE_FIELDS)
            for fact in facts
        )
        if complete_facts:
            complete += 1
        else:
            incomplete += 1
    return complete, incomplete


def trusted_metric_count(record: dict) -> int:
    trusted = 0
    for metric in (record.get("metrics") or {}).values():
        if not isinstance(metric, dict):
            continue
        value = metric.get("value")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            continue
        provenance = metric.get("provenance")
        facts = (
            provenance.get("sourceFacts")
            if isinstance(provenance, dict)
            else None
        )
        if not isinstance(facts, list) or not facts:
            continue
        if all(
            isinstance(fact, dict)
            and all(fact.get(field) not in (None, "") for field in PROVENANCE_FIELDS)
            and fact.get("consolidation") == "consolidated"
            for fact in facts
        ):
            trusted += 1
    return trusted


def source_backed_metric_count(record: dict) -> int:
    source_backed = 0
    for metric in (record.get("metrics") or {}).values():
        if not isinstance(metric, dict):
            continue
        value = metric.get("value")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            continue
        if metric.get("confidence") in {"B", "C"} and not metric.get("provenance"):
            continue
        source_backed += 1
    return source_backed


def percentage(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def add_issue(
    issues: list[dict[str, str]],
    code: str,
    severity: str,
) -> None:
    issues.append({"code": code, "severity": severity})


def audit_company(
    company: dict,
    record: dict | None,
    today: date,
) -> dict:
    code = str(company.get("code") or "")
    base = {
        "code": code,
        "companyName": str(company.get("name") or ""),
        "market": str(company.get("market") or ""),
        "industry": str(company.get("industry") or ""),
    }
    if not isinstance(record, dict):
        return {
            **base,
            "status": "missing",
            "source": None,
            "documentId": None,
            "periodEnd": None,
            "periodAgeDays": None,
            "metricCount": 0,
            "sourceBackedMetricCount": 0,
            "provenanceMetricCount": 0,
            "trustedMetricCount": 0,
            "issues": [{"code": "missing-financial-record", "severity": "missing"}],
        }

    issues: list[dict[str, str]] = []
    metrics = finite_metrics(record)
    raw_metrics = record.get("metrics") or {}
    if not metrics:
        add_issue(issues, "no-finite-metrics", "review")
    if len(metrics) != len(raw_metrics):
        add_issue(issues, "invalid-metric-value", "review")

    period_end = str(record.get("periodEnd") or "")
    try:
        period_date = date.fromisoformat(period_end)
        period_age_days = (today - period_date).days
        if period_age_days > STALE_PERIOD_DAYS:
            add_issue(issues, "stale-period", "warning")
        if period_age_days < -60:
            add_issue(issues, "future-period", "review")
    except ValueError:
        period_age_days = None
        add_issue(issues, "invalid-period", "review")

    for field in ("source", "documentId", "sourceUrl"):
        if not record.get(field):
            add_issue(issues, f"missing-{field}", "review")

    complete_provenance, incomplete_provenance = provenance_counts(record)
    if metrics and complete_provenance == 0:
        add_issue(issues, "missing-provenance", "warning")
    elif complete_provenance < len(metrics):
        add_issue(issues, "partial-provenance", "warning")
    if incomplete_provenance:
        add_issue(issues, "incomplete-provenance-facts", "warning")

    quality = record.get("quality") or {}
    if (
        record.get("source") == "EDINET"
        and int(quality.get("dataModelVersion") or 0) < MIN_EDINET_DATA_MODEL
    ):
        add_issue(issues, "old-edinet-model", "warning")
    if quality.get("roeStatus") == "quarantined-stale-model":
        add_issue(issues, "roe-quarantined", "warning")
    if quality.get("reconciliationStatus") == "quarantined":
        add_issue(issues, "source-reconciliation-quarantined", "review")

    quarantine = record.get("quarantine") or {}
    metric_validation = (
        (quarantine.get("metricValidation") or {}).get("metrics") or {}
    )
    if metric_validation:
        add_issue(issues, "metric-range-quarantined", "review")
    source_reconciliation = (
        (quarantine.get("sourceReconciliation") or {}).get("metrics") or {}
    )
    if source_reconciliation:
        add_issue(issues, "source-mismatch-quarantined", "review")
    if quarantine.get("historyTrend"):
        add_issue(issues, "history-trend-quarantined", "warning")

    severities = {issue["severity"] for issue in issues}
    status = "review" if "review" in severities else "warning" if issues else "ok"
    return {
        **base,
        "status": status,
        "source": record.get("source"),
        "documentId": record.get("documentId"),
        "periodEnd": period_end,
        "periodAgeDays": period_age_days,
        "metricCount": len(metrics),
        "sourceBackedMetricCount": source_backed_metric_count(record),
        "provenanceMetricCount": complete_provenance,
        "trustedMetricCount": trusted_metric_count(record),
        "dataModelVersion": quality.get("dataModelVersion"),
        "provenanceModelVersion": quality.get("provenanceModelVersion"),
        "issues": issues,
    }


def regression_violations(
    summary: dict,
    previous_report: dict,
) -> list[dict]:
    previous = previous_report.get("summary") or {}
    if (
        int(previous_report.get("schemaVersion") or 0) != SCHEMA_VERSION
        or not previous
    ):
        return []

    checks = (
        ("missing", "max", 0.0),
        ("review", "max", 0.0),
        ("recordsAvailable", "min", 0.0),
        ("coverageRatio", "min", RATE_TOLERANCE_POINTS),
        ("trustedMetricRatio", "min", RATE_TOLERANCE_POINTS),
        ("missingProvenanceRate", "max", RATE_TOLERANCE_POINTS),
        ("oldEdinetModelRate", "max", RATE_TOLERANCE_POINTS),
        ("metricRangeQuarantined", "max", 0.0),
        ("sourceQuarantinedMetrics", "max", 0.0),
        (
            "edinetBatchFailureRate",
            "max",
            PIPELINE_RATE_TOLERANCE_POINTS,
        ),
        (
            "tdnetStrictFailureRate",
            "max",
            PIPELINE_RATE_TOLERANCE_POINTS,
        ),
    )
    violations = []
    for field, comparison, tolerance in checks:
        if field not in previous:
            continue
        value = float(summary.get(field) or 0)
        baseline = float(previous.get(field) or 0)
        failed = (
            value > baseline + tolerance
            if comparison == "max"
            else value < baseline - tolerance
        )
        if failed:
            violations.append(
                {
                    "field": field,
                    "value": value,
                    "baseline": baseline,
                    "comparison": comparison,
                    "tolerance": tolerance,
                }
            )

    if int(summary.get("sourceQuarantinedMetrics") or 0) > 0 and not any(
        violation["field"] == "sourceQuarantinedMetrics"
        for violation in violations
    ):
        violations.append(
            {
                "field": "sourceQuarantinedMetrics",
                "value": int(summary["sourceQuarantinedMetrics"]),
                "baseline": 0,
                "comparison": "equal",
                "tolerance": 0,
            }
        )
    return violations


def build_report(
    company_master: dict,
    snapshot: dict,
    market_snapshot: dict | None = None,
    previous_report: dict | None = None,
    today: date | None = None,
) -> dict:
    today = today or datetime.now(timezone.utc).date()
    companies = company_master.get("companies") or []
    records = snapshot.get("records") or {}

    duplicate_codes = [
        code
        for code, count in Counter(
            str(company.get("code") or "") for company in companies
        ).items()
        if code and count > 1
    ]
    master_codes = {
        str(company.get("code") or "")
        for company in companies
        if company.get("code")
    }
    unknown_record_codes = sorted(set(records) - master_codes)

    audited = [
        audit_company(
            company,
            records.get(str(company.get("code") or "")),
            today,
        )
        for company in companies
    ]
    audited.sort(key=lambda company: company["code"])

    status_counts = Counter(company["status"] for company in audited)
    issue_counts = Counter(
        issue["code"]
        for company in audited
        for issue in company["issues"]
    )
    source_counts = Counter(
        str(company.get("source") or "unavailable")
        for company in audited
    )
    industry_statuses: dict[str, Counter] = defaultdict(Counter)
    for company in audited:
        industry_statuses[company["industry"]][company["status"]] += 1

    total = len(audited)
    records_available = total - status_counts["missing"]
    total_metric_count = sum(company["metricCount"] for company in audited)
    source_backed_metrics = sum(
        company["sourceBackedMetricCount"] for company in audited
    )
    trusted_metrics = sum(company["trustedMetricCount"] for company in audited)
    stats = snapshot.get("stats") or {}
    edinet_batch_failures = int(stats.get("edinetBatchFailures") or 0)
    edinet_no_metric_documents = int(stats.get("edinetNoMetricDocuments") or 0)
    edinet_batch_size = int(stats.get("edinetBatchSize") or 0)
    tdnet_strict_failures = int(stats.get("tdnetStrictFailures") or 0)
    tdnet_no_metric_documents = int(stats.get("tdnetNoMetricDocuments") or 0)
    tdnet_documents_attempted = int(
        stats.get("tdnetDocumentsAttempted")
        or stats.get("tdnetFullYearFilings")
        or 0
    )
    summary = {
        "companies": total,
        "recordsAvailable": records_available,
        "coverageRatio": percentage(records_available, total),
        "ok": status_counts["ok"],
        "warning": status_counts["warning"],
        "review": status_counts["review"],
        "missing": status_counts["missing"],
        "totalMetricCount": total_metric_count,
        "sourceBackedMetricCount": source_backed_metrics,
        "trustedMetricCount": trusted_metrics,
        "trustedMetricRatio": percentage(trusted_metrics, source_backed_metrics),
        "missingProvenanceRate": percentage(
            issue_counts["missing-provenance"],
            records_available,
        ),
        "oldEdinetModelRate": percentage(
            issue_counts["old-edinet-model"],
            source_counts["EDINET"],
        ),
        "metricRangeQuarantined": int(
            stats.get("metricRangeQuarantined") or 0
        ),
        "sourceQuarantinedMetrics": int(
            stats.get("sourceQuarantinedMetrics") or 0
        ),
        "edinetBatchSize": edinet_batch_size,
        "edinetBatchFailures": edinet_batch_failures,
        "edinetBatchFailureRate": percentage(
            edinet_batch_failures,
            edinet_batch_size,
        ),
        "edinetNoMetricDocuments": edinet_no_metric_documents,
        "edinetNoMetricRate": percentage(
            edinet_no_metric_documents,
            edinet_batch_size,
        ),
        "tdnetDocumentsAttempted": tdnet_documents_attempted,
        "tdnetStrictFailures": tdnet_strict_failures,
        "tdnetStrictFailureRate": percentage(
            tdnet_strict_failures,
            tdnet_documents_attempted,
        ),
        "tdnetNoMetricDocuments": tdnet_no_metric_documents,
        "tdnetNoMetricRate": percentage(
            tdnet_no_metric_documents,
            tdnet_documents_attempted,
        ),
        "pipelineFailureCount": (
            edinet_batch_failures + tdnet_strict_failures
        ),
        "unusableDocumentCount": (
            edinet_no_metric_documents + tdnet_no_metric_documents
        ),
        "issueCounts": dict(sorted(issue_counts.items())),
        "sourceCounts": dict(sorted(source_counts.items())),
    }
    industries = {
        industry: {
            "companies": sum(counts.values()),
            "ok": counts["ok"],
            "warning": counts["warning"],
            "review": counts["review"],
            "missing": counts["missing"],
            "coverageRatio": round(
                (sum(counts.values()) - counts["missing"])
                / sum(counts.values())
                * 100,
                2,
            ),
        }
        for industry, counts in sorted(industry_statuses.items())
    }
    metric_coverage = build_metric_coverage(
        audited,
        records,
        market_snapshot,
    )

    violations = regression_violations(summary, previous_report or {})
    if int(company_master.get("companyCount") or 0) != total:
        violations.append(
            {
                "field": "masterCompanyCount",
                "value": total,
                "baseline": int(company_master.get("companyCount") or 0),
                "comparison": "equal",
            }
        )
    if duplicate_codes:
        violations.append(
            {
                "field": "duplicateMasterCodes",
                "value": len(duplicate_codes),
                "baseline": 0,
                "comparison": "max",
            }
        )
    if unknown_record_codes:
        violations.append(
            {
                "field": "unknownFinancialRecordCodes",
                "value": len(unknown_record_codes),
                "baseline": 0,
                "comparison": "max",
            }
        )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now(),
        "financialSnapshotGeneratedAt": snapshot.get("generatedAt"),
        "policy": {
            "stalePeriodDays": STALE_PERIOD_DAYS,
            "minimumEdinetDataModelVersion": MIN_EDINET_DATA_MODEL,
            "regressionChecks": [
                "missing and review must not increase",
                "coverage and trusted metric ratio must not decrease",
                "missing provenance and old model rates must not increase",
                "metric and source quarantine counts must not increase",
                "pipeline failure rates must not increase",
                "no-metric document rates are reported for changing cohorts",
                "any source mismatch quarantine requires review",
            ],
            "schemaNote": (
                "Version 2 resets the baseline after the financial snapshot "
                "moved to generated fallback records without sourceFacts. "
                "Missing sourceFacts remain warning issues and UI confidence "
                "is downgraded, while hard range and source mismatches still "
                "block the gate."
            ),
            "rateTolerancePoints": RATE_TOLERANCE_POINTS,
            "pipelineRateTolerancePoints": PIPELINE_RATE_TOLERANCE_POINTS,
        },
        "summary": summary,
        "metricCoverage": metric_coverage,
        "industries": industries,
        "integrity": {
            "duplicateMasterCodes": duplicate_codes,
            "unknownFinancialRecordCodes": unknown_record_codes,
        },
        "violations": violations,
        "companies": audited,
    }


def write_actions_summary(report: dict) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    summary = report["summary"]
    violations = report["violations"]
    status = "FAIL" if violations else "PASS"
    lines = [
        f"## All-company quality gate: {status}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Coverage | {summary['coverageRatio']:.2f}% |",
        f"| Trusted KPI ratio | {summary['trustedMetricRatio']:.2f}% |",
        f"| Missing provenance rate | {summary['missingProvenanceRate']:.2f}% |",
        f"| Old EDINET model rate | {summary['oldEdinetModelRate']:.2f}% |",
        f"| Review companies | {summary['review']} |",
        f"| Missing companies | {summary['missing']} |",
        f"| EDINET batch failure rate | {summary['edinetBatchFailureRate']:.2f}% |",
        f"| EDINET no-metric rate | {summary['edinetNoMetricRate']:.2f}% |",
        f"| TDnet strict failure rate | {summary['tdnetStrictFailureRate']:.2f}% |",
        f"| TDnet no-metric rate | {summary['tdnetNoMetricRate']:.2f}% |",
        "",
    ]
    if violations:
        lines.extend(
            [
                "### Violations",
                "",
                "~~~json",
                json.dumps(violations, ensure_ascii=False, indent=2),
                "~~~",
                "",
            ]
        )
    with Path(summary_path).open("a", encoding="utf-8") as output:
        output.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    previous_report = load_json(args.output)
    report = build_report(
        load_json(COMPANY_MASTER),
        load_json(FINANCIALS),
        load_json(MARKET),
        previous_report=previous_report,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    write_actions_summary(report)
    summary = report["summary"]
    print(
        "All-company audit: "
        f"{summary['companies']} companies, "
        f"{summary['recordsAvailable']} available, "
        f"{summary['ok']} ok, "
        f"{summary['warning']} warning, "
        f"{summary['review']} review, "
        f"{summary['missing']} missing, "
        f"{summary['trustedMetricRatio']:.2f}% trusted KPIs, "
        f"{summary['pipelineFailureCount']} pipeline failures, "
        f"{summary['unusableDocumentCount']} no-metric documents."
    )
    if report["violations"]:
        print(json.dumps(report["violations"], ensure_ascii=False))
        return 1 if args.check else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
