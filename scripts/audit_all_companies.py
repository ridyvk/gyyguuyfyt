#!/usr/bin/env python3
"""Generate a nightly audit report for the complete JPX company universe."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANY_MASTER = ROOT / "src" / "data" / "listedCompanies.json"
FINANCIALS = ROOT / "public" / "data" / "financials.json"
DEFAULT_OUTPUT = ROOT / "public" / "data" / "all-company-audit.json"

SCHEMA_VERSION = 1
MIN_EDINET_DATA_MODEL = 9
STALE_PERIOD_DAYS = 800
PROVENANCE_FIELDS = ("tag", "contextRef", "unitRef", "consolidation")


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
            "provenanceMetricCount": 0,
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
        "provenanceMetricCount": complete_provenance,
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
        ("missing", "max"),
        ("review", "max"),
        ("recordsAvailable", "min"),
    )
    violations = []
    for field, comparison in checks:
        value = int(summary.get(field) or 0)
        baseline = int(previous.get(field) or 0)
        failed = value > baseline if comparison == "max" else value < baseline
        if failed:
            violations.append(
                {
                    "field": field,
                    "value": value,
                    "baseline": baseline,
                    "comparison": comparison,
                }
            )
    return violations


def build_report(
    company_master: dict,
    snapshot: dict,
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
    summary = {
        "companies": total,
        "recordsAvailable": records_available,
        "coverageRatio": (
            round(records_available / total * 100, 2) if total else 0
        ),
        "ok": status_counts["ok"],
        "warning": status_counts["warning"],
        "review": status_counts["review"],
        "missing": status_counts["missing"],
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
                "missing must not increase",
                "review must not increase",
                "recordsAvailable must not decrease",
            ],
        },
        "summary": summary,
        "industries": industries,
        "integrity": {
            "duplicateMasterCodes": duplicate_codes,
            "unknownFinancialRecordCodes": unknown_record_codes,
        },
        "violations": violations,
        "companies": audited,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    previous_report = load_json(args.output)
    report = build_report(
        load_json(COMPANY_MASTER),
        load_json(FINANCIALS),
        previous_report=previous_report,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print(
        "All-company audit: "
        f"{summary['companies']} companies, "
        f"{summary['recordsAvailable']} available, "
        f"{summary['ok']} ok, "
        f"{summary['warning']} warning, "
        f"{summary['review']} review, "
        f"{summary['missing']} missing."
    )
    if report["violations"]:
        print(json.dumps(report["violations"], ensure_ascii=False))
        return 1 if args.check else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
