#!/usr/bin/env python3
"""Validate generated company, financial, and market datasets."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data_quality import is_iso_date, normalize_security_code, validate_financial_record

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "src/data/listedCompanies.json"
FINANCIALS = ROOT / "public/data/financials.json"
MARKET = ROOT / "public/data/market.json"
DISCLOSURES = ROOT / "public/data/disclosures.json"
JST = timezone(timedelta(hours=9))
MAX_MARKET_DATA_AGE_DAYS = 7


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
    if int(payload.get("schemaVersion") or 0) < 3:
        errors.append("market schemaVersion must be at least 3")
    latest_trading_date = str(payload.get("latestTradingDate") or "")
    if not is_iso_date(latest_trading_date):
        errors.append("market latestTradingDate is invalid")
    else:
        latest_date = datetime.fromisoformat(latest_trading_date).date()
        today_jst = datetime.now(JST).date()
        if (today_jst - latest_date).days > MAX_MARKET_DATA_AGE_DAYS:
            errors.append(
                "market latestTradingDate is too old: "
                f"{latest_trading_date}"
            )

    missing_quote_codes = sorted(codes - set(quotes))
    if missing_quote_codes:
        sample = ", ".join(missing_quote_codes[:10])
        errors.append(
            f"market is missing {len(missing_quote_codes)} company quote(s): {sample}"
        )

    quote_dates: list[str] = []
    for code, quote in quotes.items():
        if code not in codes:
            errors.append(f"market quote {code} is not in company master")
            continue
        if not isinstance(quote, dict) or not is_iso_date(quote.get("date")):
            errors.append(f"market quote {code} has invalid date")
            continue
        quote_dates.append(str(quote["date"]))
        close = quote.get("close")
        if not isinstance(close, (int, float)) or not math.isfinite(close) or close <= 0:
            errors.append(f"market quote {code} has invalid close")
    latest_quote_date = max(quote_dates, default="")
    if latest_trading_date and latest_quote_date and latest_trading_date != latest_quote_date:
        errors.append(
            "market latestTradingDate does not match quote max date: "
            f"{latest_trading_date} != {latest_quote_date}"
        )
    stale_flag_errors = [
        code
        for code, quote in quotes.items()
        if isinstance(quote, dict)
        and is_iso_date(quote.get("date"))
        and str(quote["date"]) < latest_quote_date
        and not quote.get("stale")
    ]
    if stale_flag_errors:
        sample = ", ".join(stale_flag_errors[:10])
        errors.append(
            f"market has {len(stale_flag_errors)} older quote(s) without stale=true: {sample}"
        )
    stats_count = int((payload.get("stats") or {}).get("companies") or 0)
    if stats_count != len(quotes):
        errors.append(f"market stats companies={stats_count} but quotes={len(quotes)}")
    return errors


def validate_disclosures(codes: set[str]) -> list[str]:
    payload = load(DISCLOSURES)
    events = payload.get("events", []) or []
    stats = payload.get("stats", {}) or {}
    errors: list[str] = []
    if int(payload.get("schemaVersion") or 0) != 1:
        errors.append("disclosures schemaVersion must be 1")
    if not isinstance(events, list):
        return ["disclosures events must be a list"]
    if int(stats.get("events") or 0) != len(events):
        errors.append(
            f"disclosure stats events={stats.get('events')} but events={len(events)}"
        )

    event_ids: set[str] = set()
    event_codes: set[str] = set()
    filed_at_values: list[str] = []
    valid_sources = {"TDnet", "EDINET"}
    valid_importance = {"critical", "high", "medium", "low"}
    valid_categories = {
        "earnings",
        "guidance",
        "dividend",
        "buyback",
        "ma",
        "capital",
        "finance",
        "governance",
        "personnel",
        "large-holding",
        "annual-report",
        "correction",
        "other",
    }
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"disclosure event {index} is not an object")
            continue
        event_id = str(event.get("id") or "")
        code = str(event.get("code") or "")
        filed_at = str(event.get("filedAt") or "")
        if not event_id:
            errors.append(f"disclosure event {index} has no id")
        elif event_id in event_ids:
            errors.append(f"disclosures contain duplicate id {event_id}")
        event_ids.add(event_id)
        if code not in codes:
            errors.append(f"disclosure event {event_id} has unknown code {code}")
        event_codes.add(code)
        try:
            datetime.fromisoformat(filed_at.replace("Z", "+00:00"))
            filed_at_values.append(filed_at)
        except (TypeError, ValueError):
            errors.append(f"disclosure event {event_id} has invalid filedAt")
        if event.get("source") not in valid_sources:
            errors.append(f"disclosure event {event_id} has invalid source")
        if event.get("importance") not in valid_importance:
            errors.append(f"disclosure event {event_id} has invalid importance")
        if event.get("category") not in valid_categories:
            errors.append(f"disclosure event {event_id} has invalid category")
        if not str(event.get("title") or "").strip():
            errors.append(f"disclosure event {event_id} has no title")
        if not str(event.get("url") or "").startswith("https://"):
            errors.append(f"disclosure event {event_id} has invalid url")

    if int(stats.get("companies") or 0) != len(event_codes):
        errors.append(
            "disclosure stats companies does not match unique event companies"
        )
    latest_filed_at = str(payload.get("latestFiledAt") or "")
    if filed_at_values and latest_filed_at != max(filed_at_values):
        errors.append("disclosure latestFiledAt does not match the newest event")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=("all", "master", "financial", "market", "disclosure"),
        default="all",
    )
    args = parser.parse_args()

    codes, errors = validate_master()
    if args.scope in {"all", "financial"}:
        errors.extend(validate_financials(codes))
    if args.scope in {"all", "market"}:
        errors.extend(validate_market(codes))
    if args.scope in {"all", "disclosure"}:
        errors.extend(validate_disclosures(codes))

    if errors:
        for error in errors[:100]:
            print(f"error: {error}", file=sys.stderr)
        print(f"Dataset validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Dataset validation passed for scope={args.scope}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
