#!/usr/bin/env python3
"""Audit the live financial snapshot for the fixed golden-company cohort."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CASES = ROOT / "src/lib/goldenIndustryCases.ts"
COMPANY_MASTER = ROOT / "src/data/listedCompanies.json"
FINANCIALS = ROOT / "public/data/financials.json"
DEFAULT_OUTPUT = ROOT / "public/data/golden-company-audit.json"

CASE_PATTERN = re.compile(
    r"\{\s*\n"
    r"\s*code: '([^']+)',\s*\n"
    r"\s*companyName: '([^']+)',\s*\n"
    r"\s*industry: '([^']+)',\s*\n"
    r".*?"
    r"\s*riskFlags: (\[[^\]]*\]),\s*\n"
    r"\s*minimumKpis:",
    re.DOTALL,
)
STRING_PATTERN = re.compile(r"'([^']+)'")

# The first committed audit establishes non-regression budgets. Improvements pass.
MAX_MISSING_RECORDS = 4
MAX_ROE_QUARANTINED = 23
MAX_WITHOUT_PROVENANCE = 33
MAX_OLD_EDINET_MODELS = 30
MIN_HEALTHY_RECORDS = 7
MIN_EDINET_DATA_MODEL = 9


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases(path: Path = GOLDEN_CASES) -> list[dict]:
    source = path.read_text(encoding="utf-8")
    return [
        {
            "code": code,
            "companyName": company_name,
            "industry": industry,
            "riskFlags": STRING_PATTERN.findall(risk_flags),
        }
        for code, company_name, industry, risk_flags in CASE_PATTERN.findall(source)
    ]


def finite_metrics(record: dict) -> dict[str, float]:
    result = {}
    for key, metric in (record.get("metrics") or {}).items():
        value = metric.get("value") if isinstance(metric, dict) else None
        if isinstance(value, (int, float)) and math.isfinite(value):
            result[str(key)] = float(value)
    return result


def provenance_metric_count(record: dict) -> int:
    return sum(
        1
        for metric in (record.get("metrics") or {}).values()
        if isinstance(metric, dict)
        and isinstance(metric.get("provenance"), dict)
        and bool(metric["provenance"].get("sourceFacts"))
    )


def audit_case(
    case: dict,
    record: dict | None,
    master_company: dict | None,
    today: date,
) -> dict:
    issues: list[dict[str, str]] = []
    if master_company is None:
        issues.append({"code": "missing-master", "severity": "critical"})
    elif str(master_company.get("industry") or "") != case["industry"]:
        issues.append({"code": "industry-mismatch", "severity": "critical"})

    if not isinstance(record, dict):
        issues.append({"code": "missing-record", "severity": "warning"})
        return {
            **case,
            "source": None,
            "periodEnd": None,
            "metricCount": 0,
            "provenanceMetricCount": 0,
            "issues": issues,
            "status": "warning",
        }

    metrics = finite_metrics(record)
    raw_metrics = record.get("metrics") or {}
    if not metrics:
        issues.append({"code": "no-finite-metrics", "severity": "critical"})
    if len(metrics) != len(raw_metrics):
        issues.append({"code": "invalid-metric-value", "severity": "critical"})

    period_end_text = str(record.get("periodEnd") or "")
    try:
        age_days = (today - date.fromisoformat(period_end_text)).days
        if age_days > 800:
            issues.append({"code": "stale-period", "severity": "warning"})
    except ValueError:
        age_days = None
        issues.append({"code": "invalid-period", "severity": "critical"})

    quality = record.get("quality") or {}
    if quality.get("roeStatus") == "quarantined-stale-model":
        issues.append({"code": "roe-quarantined", "severity": "warning"})

    if (
        record.get("source") == "EDINET"
        and int(quality.get("dataModelVersion") or 0) < MIN_EDINET_DATA_MODEL
    ):
        issues.append({"code": "old-edinet-model", "severity": "warning"})

    provenance_count = provenance_metric_count(record)
    if provenance_count == 0:
        issues.append({"code": "missing-provenance", "severity": "warning"})

    if "low-roe-not-zero" in case["riskFlags"]:
        roe = metrics.get("roe")
        if roe is None or roe == 0:
            issues.append({"code": "low-roe-regressed-to-zero", "severity": "critical"})

    severity = {issue["severity"] for issue in issues}
    status = "critical" if "critical" in severity else "warning" if issues else "ok"
    return {
        **case,
        "source": record.get("source"),
        "periodEnd": period_end_text,
        "periodAgeDays": age_days,
        "metricCount": len(metrics),
        "provenanceMetricCount": provenance_count,
        "roe": metrics.get("roe"),
        "dataModelVersion": quality.get("dataModelVersion"),
        "provenanceModelVersion": quality.get("provenanceModelVersion"),
        "issues": issues,
        "status": status,
    }


def build_report(
    cases: list[dict],
    snapshot: dict,
    company_master: dict,
    today: date | None = None,
) -> dict:
    today = today or datetime.now(timezone.utc).date()
    records = snapshot.get("records") or {}
    master_by_code = {
        str(company.get("code") or ""): company
        for company in company_master.get("companies", [])
    }
    audited = [
        audit_case(
            case,
            records.get(case["code"]),
            master_by_code.get(case["code"]),
            today,
        )
        for case in cases
    ]
    issue_counts = Counter(
        issue["code"]
        for company in audited
        for issue in company["issues"]
    )
    status_counts = Counter(company["status"] for company in audited)

    summary = {
        "companies": len(audited),
        "healthy": status_counts["ok"],
        "warning": status_counts["warning"],
        "critical": status_counts["critical"],
        "missingRecords": issue_counts["missing-record"],
        "roeQuarantined": issue_counts["roe-quarantined"],
        "withoutProvenance": issue_counts["missing-provenance"],
        "oldEdinetModels": issue_counts["old-edinet-model"],
        "issueCounts": dict(sorted(issue_counts.items())),
    }
    violations = []
    checks = (
        ("missingRecords", MAX_MISSING_RECORDS, "max"),
        ("roeQuarantined", MAX_ROE_QUARANTINED, "max"),
        ("withoutProvenance", MAX_WITHOUT_PROVENANCE, "max"),
        ("oldEdinetModels", MAX_OLD_EDINET_MODELS, "max"),
        ("healthy", MIN_HEALTHY_RECORDS, "min"),
        ("critical", 0, "max"),
    )
    for field, limit, mode in checks:
        value = int(summary[field])
        failed = value > limit if mode == "max" else value < limit
        if failed:
            violations.append(
                {
                    "field": field,
                    "value": value,
                    "limit": limit,
                    "comparison": mode,
                }
            )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "financialSnapshotGeneratedAt": snapshot.get("generatedAt"),
        "baseline": {
            "maxMissingRecords": MAX_MISSING_RECORDS,
            "maxRoeQuarantined": MAX_ROE_QUARANTINED,
            "maxWithoutProvenance": MAX_WITHOUT_PROVENANCE,
            "maxOldEdinetModels": MAX_OLD_EDINET_MODELS,
            "minHealthyRecords": MIN_HEALTHY_RECORDS,
        },
        "summary": summary,
        "violations": violations,
        "companies": audited,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(
        load_cases(),
        load_json(FINANCIALS),
        load_json(COMPANY_MASTER),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    print(
        "Golden audit: "
        f"{summary['companies']} companies, "
        f"{summary['healthy']} healthy, "
        f"{summary['warning']} warnings, "
        f"{summary['critical']} critical"
    )
    if report["violations"]:
        print(json.dumps(report["violations"], ensure_ascii=False))
        return 1 if args.check else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
