#!/usr/bin/env python3
"""Validate generated company, financial, and market datasets."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data_quality import is_iso_date, normalize_security_code, validate_financial_record

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "src/data/listedCompanies.json"
FINANCIALS = ROOT / "public/data/financials.json"
MARKET = ROOT / "public/data/market.json"
MARKET_STATUS = ROOT / "public/data/market-status.json"
DISCLOSURES = ROOT / "public/data/disclosures.json"
DISCLOSURE_MANIFEST = ROOT / "public/data/disclosures/manifest.json"
JST = timezone(timedelta(hours=9))
MAX_MARKET_DATA_AGE_DAYS = 7
MIN_MARKET_QUOTE_COVERAGE_RATIO = 99.5
MAX_MARKET_MISSING_QUOTES = 25


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_disclosure_snapshot() -> dict:
    if DISCLOSURES.exists():
        return load(DISCLOSURES)
    manifest = load(DISCLOSURE_MANIFEST)
    if int(manifest.get("schemaVersion") or 0) != 1:
        raise ValueError("disclosure shard manifest schemaVersion must be 1")
    events: list[dict] = []
    for entry in manifest.get("shards") or []:
        filename = str((entry or {}).get("file") or "")
        if not re.fullmatch(r"chunk-\d{3}\.json", filename):
            raise ValueError(f"invalid disclosure shard filename: {filename}")
        shard = load(DISCLOSURE_MANIFEST.parent / filename)
        if shard.get("generatedAt") != manifest.get("generatedAt"):
            raise ValueError(f"disclosure shard generation mismatch: {filename}")
        shard_events = shard.get("events") or []
        if len(shard_events) != int(entry.get("eventCount") or 0):
            raise ValueError(f"disclosure shard count mismatch: {filename}")
        events.extend(shard_events)
    if len(events) != int(manifest.get("eventCount") or 0):
        raise ValueError("disclosure manifest event count mismatch")
    return {**(manifest.get("snapshot") or {}), "events": events}


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

    quoted_codes = codes & set(quotes)
    missing_quote_codes = sorted(codes - set(quotes))
    coverage_ratio = len(quoted_codes) / len(codes) * 100 if codes else 0.0
    if missing_quote_codes:
        sample = ", ".join(missing_quote_codes[:10])
        if (
            coverage_ratio < MIN_MARKET_QUOTE_COVERAGE_RATIO
            or len(missing_quote_codes) > MAX_MARKET_MISSING_QUOTES
        ):
            errors.append(
                "market quote coverage is too low: "
                f"{coverage_ratio:.4f}% with {len(missing_quote_codes)} missing "
                f"company quote(s): {sample}"
            )
        if payload.get("status") != "partial":
            errors.append(
                "market has missing company quotes but status is not partial: "
                f"{len(missing_quote_codes)} missing ({sample})"
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
    stats = payload.get("stats") or {}
    stats_count = int(stats.get("companies") or 0)
    if stats_count != len(quotes):
        errors.append(f"market stats companies={stats_count} but quotes={len(quotes)}")
    stats_universe = int(stats.get("quoteUniverse") or 0)
    if stats_universe != len(codes):
        errors.append(
            f"market stats quoteUniverse={stats_universe} but master={len(codes)}"
        )
    stats_missing = int(stats.get("missingQuotes") or 0)
    if stats_missing != len(missing_quote_codes):
        errors.append(
            f"market stats missingQuotes={stats_missing} but missing={len(missing_quote_codes)}"
        )
    if sorted(stats.get("missingQuoteCodes") or []) != missing_quote_codes:
        errors.append("market stats missingQuoteCodes does not match missing quotes")
    if "quoteCoverageRatio" in stats or missing_quote_codes:
        try:
            stats_coverage = float(stats.get("quoteCoverageRatio"))
        except (TypeError, ValueError):
            stats_coverage = -1.0
        if abs(stats_coverage - coverage_ratio) > 0.01:
            errors.append(
                "market stats quoteCoverageRatio does not match quote coverage: "
                f"{stats_coverage} != {coverage_ratio:.4f}"
            )

    if MARKET_STATUS.exists():
        marker = load(MARKET_STATUS)
        expected_marker = {
            "generatedAt": payload.get("generatedAt"),
            "source": payload.get("source"),
            "status": payload.get("status"),
            "latestTradingDate": payload.get("latestTradingDate"),
            "latestQuoteTimestamp": payload.get("latestQuoteTimestamp"),
            "quoteUniverse": len(codes),
            "companies": len(quotes),
            "missingQuotes": len(missing_quote_codes),
            "missingQuoteCodes": missing_quote_codes,
        }
        if int(marker.get("schemaVersion") or 0) != 1:
            errors.append("market status schemaVersion must be 1")
        for key, expected in expected_marker.items():
            if marker.get(key) != expected:
                errors.append(f"market status {key} does not match market snapshot")
        try:
            marker_coverage = float(marker.get("quoteCoverageRatio"))
        except (TypeError, ValueError):
            marker_coverage = -1.0
        if abs(marker_coverage - coverage_ratio) > 0.01:
            errors.append("market status quoteCoverageRatio does not match market snapshot")
    return errors


def validate_disclosures(codes: set[str]) -> list[str]:
    try:
        payload = load_disclosure_snapshot()
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as error:
        return [f"disclosure snapshot could not be loaded: {error}"]
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
