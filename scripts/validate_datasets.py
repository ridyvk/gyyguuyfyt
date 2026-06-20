#!/usr/bin/env python3
"""Validate generated company, financial, and market datasets."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from data_quality import is_iso_date, normalize_security_code, validate_financial_record

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "src/data/listedCompanies.json"
FINANCIALS = ROOT / "public/data/financials.json"
MARKET = ROOT / "public/data/market.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_master() -> tuple[set[str], list[str]]:
    payload = load(MASTER)
    companies = payload.get("companies", [])
    errors: list[str] = []
    codes: set[str] = set()
    for index, company in enumerate(companies):
        code = str((company or {}).get("code") or "")
        if normalize_security_code(code) != code:
            continue
        if code in codes:
            errors.append(f"master contains duplicate code {code}")
        codes.add(code)
    if int(payload.get("companyCount") or 0) != len(companies):
        errors.append("master companyCount does not match companies length")
    if len(codes) < 3000:
        errors.append(f"master company universe is unexpectedly small: {len(codes)}")
    return codes, errors


def validate_financials(codes: set[str]) -> list[str]:
    payload = load(FINANCIALS)
    records = payload.get("records", {}) or {}
    errors = [
        f"financial record {code}: {reason}"
        for code, record in records.items()
        if (reason := validate_financial_record(str(code), record, codes))
    ]
    stats_count = int((payload.get("stats") or {}).get("companies") or 0)
    if stats_count != len(records):
        errors.append(
            f"financial stats companies={stats_count} but records={len(records)}"
        )
    if payload.get("status") == "ready" and (
        int((payload.get("stats") or {}).get("edinetBatchFailures") or 0)
        or int((payload.get("stats") or {}).get("tdnetStrictFailures") or 0)
    ):
        errors.append("financial status is ready despite pipeline failures")
    return errors


def validate_market(codes: set[str]) -> list[str]:
    payload = load(MARKET)
    quotes = payload.get("quotes", {}) or {}
    errors: list[str] = []
    for code, quote in quotes.items():
        if code not in codes:
            errors.append(f"market quote {code} is not in company master")
            continue
        if not isinstance(quote, dict) or not is_iso_date(quote.get("date")):
            errors.append(f"market quote {code} has invalid date")
            continue
        close = quote.get("close")
        if not isinstance(close, (int, float)) or not math.isfinite(close) or close <= 0:
            errors.append(f"market quote {code} has invalid close")
    stats_count = int((payload.get("stats") or {}).get("companies") or 0)
    if stats_count != len(quotes):
        errors.append(f"market stats companies={stats_count} but quotes={len(quotes)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=("all", "master", "financial", "market"),
        default="all",
    )
    args = parser.parse_args()

    codes, errors = validate_master()
    if args.scope in {"all", "financial"}:
        errors.extend(validate_financials(codes))
    if args.scope in {"all", "market"}:
        errors.extend(validate_market(codes))

    if errors:
        for error in errors[:100]:
            print(f"error: {error}", file=sys.stderr)
        print(f"Dataset validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Dataset validation passed for scope={args.scope}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
