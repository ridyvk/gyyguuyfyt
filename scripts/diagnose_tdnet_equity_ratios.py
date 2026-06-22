#!/usr/bin/env python3
"""Print TDnet ratio-related facts for targeted recovery diagnostics."""

from __future__ import annotations

import argparse
import json

import update_tdnet_financials_strict as strict
from data_quality import quarantine_invalid_metrics
from update_tdnet_financials import get

RELEVANT_TOKENS = ("equity", "asset", "capital", "netassets", "ratio")


def diagnostic_for(code: str, filing: dict) -> dict:
    archive = get(filing["xbrlUrl"])
    contexts, facts = strict.parse_inline_xbrl(archive)
    relevant: dict[str, list[dict]] = {}
    for concept, entries in sorted(facts.items()):
        if not any(token in concept.lower() for token in RELEVANT_TOKENS):
            continue
        relevant[concept] = [
            {
                "contextRef": context_id,
                "value": value,
                "context": contexts.get(context_id),
                "detail": detail,
            }
            for context_id, value, detail in entries
        ]

    record = strict.build_record(filing, archive)
    quarantine_invalid_metrics(record)
    return {
        "code": code,
        "filing": {
            key: filing.get(key)
            for key in ("documentId", "title", "filedAt", "xbrlUrl")
        },
        "periodEnd": record.get("periodEnd"),
        "equityRatio": (record.get("metrics") or {}).get("equityRatio"),
        "metricValidation": (
            (record.get("quarantine") or {}).get("metricValidation")
        ),
        "relevantFacts": relevant,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-days", type=int, default=460)
    parser.add_argument("--code", action="append", required=True)
    args = parser.parse_args()

    filings, _ = strict.list_full_year_filings(args.scan_days)
    for code in args.code:
        filing = filings.get(code)
        if filing is None:
            print(json.dumps({"code": code, "error": "filing-not-found"}))
            continue
        print(json.dumps(diagnostic_for(code, filing), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
