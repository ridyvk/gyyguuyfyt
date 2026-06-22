#!/usr/bin/env python3
"""Print TDnet ratio-related facts for targeted recovery diagnostics."""

from __future__ import annotations

import argparse
import json

import update_tdnet_financials_strict as strict
from data_quality import quarantine_invalid_metrics
from update_tdnet_financials import get

RELEVANT_TOKENS = ("equity", "asset", "capital", "netassets", "ratio")

KNOWN_FILINGS = {
    "2338": {
        "code": "2338",
        "companyName": "クオンタムソリューションズ",
        "documentId": "140120260410501953",
        "title": "2026年2月期 決算短信〔日本基準〕（連結）",
        "filedAt": "2026-04-14T16:00:00+09:00",
        "pdfUrl": "https://www2.jpx.co.jp/disc/23380/140120260410501953.pdf",
        "xbrlUrl": "https://www.release.tdnet.info/inbs/140120260410501953.zip",
    },
    "4592": {
        "code": "4592",
        "companyName": "サンバイオ",
        "documentId": "140120260317583272",
        "title": "2026年1月期 決算短信〔日本基準〕（連結）",
        "filedAt": "2026-03-17T15:00:00+09:00",
        "pdfUrl": "https://www2.jpx.co.jp/disc/45920/140120260317583272.pdf",
        "xbrlUrl": "https://www.release.tdnet.info/inbs/140120260317583272.zip",
    },
}


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
        filing = filings.get(code) or KNOWN_FILINGS.get(code)
        if filing is None:
            print(json.dumps({"code": code, "error": "filing-not-found"}))
            continue
        try:
            print(json.dumps(diagnostic_for(code, filing), ensure_ascii=False))
        except Exception as error:
            print(
                json.dumps(
                    {
                        "code": code,
                        "error": str(error),
                        "xbrlUrl": filing.get("xbrlUrl"),
                    },
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
