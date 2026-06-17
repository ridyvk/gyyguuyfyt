#!/usr/bin/env python3
"""Run the EDINET updater as a stricter annual baseline builder."""

from __future__ import annotations

import json
from pathlib import Path

import update_edinet_financials as edinet

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "public/data/financials.json"
MIN_EDINET_BASELINE_COMPANIES = 2500

STRICT_FACT_NAMES = {
    **edinet.FACT_NAMES,
    "revenue": tuple(
        name
        for name in edinet.FACT_NAMES["revenue"]
        if name != "OrdinaryIncome"
    ),
}


def force_bootstrap_if_needed() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    records = snapshot.get("records", {}) or {}
    edinet_count = sum(
        1
        for record in records.values()
        if isinstance(record, dict) and record.get("source") == "EDINET"
    )
    if edinet_count >= MIN_EDINET_BASELINE_COMPANIES:
        return
    snapshot["schemaVersion"] = 0
    snapshot.setdefault("stats", {})["edinetBootstrapForced"] = True
    snapshot["stats"]["edinetCompaniesBeforeBootstrap"] = edinet_count
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Forcing EDINET bootstrap because annual baseline is incomplete: "
        f"{edinet_count} EDINET companies."
    )


def annotate_edinet_records() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for record in (snapshot.get("records", {}) or {}).values():
        if not isinstance(record, dict) or record.get("source") != "EDINET":
            continue
        record.setdefault("documentType", "AnnualSecuritiesReport")
        record.setdefault("periodType", "annual")
        record.setdefault("sourceDetail", "EDINET有価証券報告書XBRL・年次")
        record.setdefault(
            "quality",
            {
                "policy": "strict-annual-baseline",
                "edinetAnnualReport": True,
                "ambiguousRevenueTagsExcluded": ["OrdinaryIncome"],
            },
        )
    snapshot.setdefault("dataPolicy", {})
    snapshot["dataPolicy"].update(
        {
            "edinetBaseline": True,
            "edinetRevenuePolicy": "OrdinaryIncome is not used as revenue",
        }
    )
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    edinet.FACT_NAMES = STRICT_FACT_NAMES
    force_bootstrap_if_needed()
    result = edinet.main()
    if result == 0:
        annotate_edinet_records()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
