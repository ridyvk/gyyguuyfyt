#!/usr/bin/env python3
"""Refresh data/market.json with the latest Yahoo Finance market quotes."""

from __future__ import annotations

import glob
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
MARKET_PATH = DATA_DIR / "market.json"

JST = timezone(timedelta(hours=9))
SOURCE = "Yahoo Finance"
YAHOO_SPARK_URLS = (
    "https://query1.finance.yahoo.com/v7/finance/spark",
    "https://query2.finance.yahoo.com/v7/finance/spark",
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

DOMESTIC_MARKETS = {
    "\u30d7\u30e9\u30a4\u30e0\uff08\u5185\u56fd\u682a\u5f0f\uff09",
    "\u30b9\u30bf\u30f3\u30c0\u30fc\u30c9\uff08\u5185\u56fd\u682a\u5f0f\uff09",
    "\u30b0\u30ed\u30fc\u30b9\uff08\u5185\u56fd\u682a\u5f0f\uff09",
}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def load_universe() -> list[dict[str, str]]:
    files = sorted(glob.glob(str(ASSETS_DIR / "companyUniverse-*.js")))
    if not files:
        raise FileNotFoundError("assets/companyUniverse-*.js was not found")

    text = Path(files[0]).read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{code:`(?P<code>[^`]+)`,name:`(?P<name>[^`]+)`,market:`(?P<market>[^`]+)`,industry:`(?P<industry>[^`]+)`\}"
    )
    rows = [match.groupdict() for match in pattern.finditer(text)]
    if not rows:
        raise ValueError(f"No companies could be parsed from {files[0]}")
    return rows


def quote_targets(universe: list[dict[str, str]]) -> list[dict[str, str]]:
    return [company for company in universe if company["market"] in DOMESTIC_MARKETS]


def chunks(items: list[dict[str, str]], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def yahoo_symbol(code: str) -> str:
    return f"{code}.T"


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def number_or_none(value: Any) -> float | None:
    if is_number(value):
        return float(value)
    return None


def latest_numeric_pair(timestamps: list[Any], values: list[Any]) -> tuple[int, float] | None:
    for timestamp, value in reversed(list(zip(timestamps, values))):
        if is_number(timestamp) and is_number(value):
            return int(timestamp), float(value)
    return None


def previous_numeric_value(timestamps: list[Any], values: list[Any], latest_timestamp: int) -> float | None:
    previous: float | None = None
    for timestamp, value in zip(timestamps, values):
        if not is_number(timestamp) or not is_number(value):
            continue
        if int(timestamp) >= latest_timestamp:
            break
        previous = float(value)
    return previous


def fetch_json(url: str, params: dict[str, str]) -> dict[str, Any]:
    request = Request(f"{url}?{urlencode(params)}", headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_batch(companies: list[dict[str, str]]) -> dict[str, Any]:
    symbols = ",".join(yahoo_symbol(company["code"]) for company in companies)
    params = {"symbols": symbols, "range": "5d", "interval": "1d"}
    last_error: Exception | None = None

    for attempt in range(3):
        for url in YAHOO_SPARK_URLS:
            try:
                return fetch_json(url, params)
            except HTTPError as exc:
                last_error = RuntimeError(f"{url} returned HTTP {exc.code}")
            except (URLError, TimeoutError, ValueError) as exc:
                last_error = exc
        time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Yahoo Finance request failed: {last_error}")


def parse_quote(response: dict[str, Any]) -> dict[str, Any] | None:
    meta = response.get("meta") or {}
    quote = ((response.get("indicators") or {}).get("quote") or [{}])[0]
    timestamps = response.get("timestamp") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    latest_pair = latest_numeric_pair(timestamps, closes)
    regular_price = number_or_none(meta.get("regularMarketPrice"))
    regular_time = meta.get("regularMarketTime")

    if is_number(regular_time):
        timestamp = int(regular_time)
    elif latest_pair:
        timestamp = latest_pair[0]
    else:
        return None

    close = regular_price
    if close is None and latest_pair:
        close = latest_pair[1]
    if close is None or close <= 0:
        return None

    timestamp_dt = datetime.fromtimestamp(timestamp, JST)
    latest_day_start = latest_pair[0] if latest_pair else timestamp
    previous_close = previous_numeric_value(timestamps, closes, latest_day_start)
    if previous_close is None:
        previous_close = number_or_none(meta.get("previousClose"))
    if previous_close is None:
        previous_close = number_or_none(meta.get("chartPreviousClose"))

    volume = number_or_none(meta.get("regularMarketVolume"))
    if volume is None:
        volume_pair = latest_numeric_pair(timestamps, volumes)
        volume = volume_pair[1] if volume_pair else None

    quote_payload: dict[str, Any] = {
        "date": timestamp_dt.date().isoformat(),
        "timestamp": timestamp_dt.isoformat(),
        "close": close,
        "volume": volume,
        "source": SOURCE,
        "priceType": "regular-market-price",
        "isRealtime": False,
    }

    if previous_close is not None and previous_close > 0:
        quote_payload["previousClose"] = previous_close
        quote_payload["changePercent"] = round((close / previous_close - 1) * 100, 4)

    return quote_payload


def parse_spark_payload(
    payload: dict[str, Any],
    requested: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    by_symbol = {
        item.get("symbol"): item
        for item in (payload.get("spark") or {}).get("result", [])
        if item.get("symbol")
    }
    quotes: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    for company in requested:
        code = company["code"]
        item = by_symbol.get(yahoo_symbol(code))
        response = ((item or {}).get("response") or [None])[0]
        quote = parse_quote(response) if isinstance(response, dict) else None
        if quote:
            quotes[code] = quote
        else:
            failures.append(
                {
                    "code": code,
                    "name": company["name"],
                    "market": company["market"],
                    "reason": "quote-not-returned",
                }
            )

    return quotes, failures


def failure_for(company: dict[str, str], reason: str) -> dict[str, str]:
    return {
        "code": company["code"],
        "name": company["name"],
        "market": company["market"],
        "reason": reason,
    }


def fetch_quotes_for_companies(
    companies: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    try:
        payload = fetch_batch(companies)
        return parse_spark_payload(payload, companies)
    except RuntimeError as exc:
        if len(companies) == 1:
            return {}, [failure_for(companies[0], str(exc))]

        midpoint = len(companies) // 2
        left_quotes, left_failures = fetch_quotes_for_companies(companies[:midpoint])
        right_quotes, right_failures = fetch_quotes_for_companies(companies[midpoint:])
        return {**left_quotes, **right_quotes}, left_failures + right_failures


def build_payload(
    previous: dict[str, Any],
    target_companies: list[dict[str, str]],
    fresh_quotes: dict[str, dict[str, Any]],
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    previous_quotes = previous.get("quotes") or {}
    quotes: dict[str, dict[str, Any]] = {}
    stale_codes: list[str] = []

    for company in target_companies:
        code = company["code"]
        if code in fresh_quotes:
            quotes[code] = fresh_quotes[code]
        elif code in previous_quotes:
            stale_quote = dict(previous_quotes[code])
            stale_quote["stale"] = True
            quotes[code] = stale_quote
            stale_codes.append(code)

    date_counts = Counter(
        quote.get("date")
        for quote in quotes.values()
        if isinstance(quote, dict) and quote.get("date")
    )
    trading_dates = sorted(date_counts.keys(), reverse=True)[:5]
    latest_timestamps = [
        quote.get("timestamp")
        for quote in quotes.values()
        if isinstance(quote, dict) and quote.get("timestamp")
    ]

    fundamentals = previous.get("fundamentals") or {}
    previous_stats = previous.get("stats") or {}
    stats = {
        **previous_stats,
        "quoteUniverse": len(target_companies),
        "companies": len(quotes),
        "tradingDates": trading_dates,
        "fundamentals": len(fundamentals),
        "quoteFailures": len(failures),
        "freshQuotesFetched": len(fresh_quotes),
        "staleQuotesRetained": len(stale_codes),
        "quoteFailureExamples": failures[:20],
    }

    return {
        **previous,
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "status": "ready" if fresh_quotes else "partial",
        "latestTradingDate": trading_dates[0] if trading_dates else None,
        "latestQuoteTimestamp": max(latest_timestamps) if latest_timestamps else None,
        "quotes": quotes,
        "fundamentals": fundamentals,
        "stats": stats,
    }


def main() -> None:
    batch_size = max(1, env_int("MARKET_QUOTE_BATCH_SIZE", 20))
    limit = env_int("MARKET_QUOTE_LIMIT", 0)
    sleep_seconds = max(0.0, env_float("MARKET_QUOTE_SLEEP_SECONDS", 0.2))
    dry_run = os.environ.get("MARKET_QUOTE_DRY_RUN") == "1"

    previous = load_json(MARKET_PATH, {"quotes": {}, "fundamentals": {}, "stats": {}})
    universe = load_universe()
    target_companies = quote_targets(universe)
    if limit > 0:
        target_companies = target_companies[:limit]

    fresh_quotes: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []

    batches = list(chunks(target_companies, batch_size))
    for index, batch in enumerate(batches, start=1):
        batch_quotes, batch_failures = fetch_quotes_for_companies(batch)
        fresh_quotes.update(batch_quotes)
        failures.extend(batch_failures)
        print(
            "batch {index}/{total}: requested={requested} fresh={fresh} failed={failed}".format(
                index=index,
                total=len(batches),
                requested=len(batch),
                fresh=len(batch_quotes),
                failed=len(batch_failures),
            )
        )
        if sleep_seconds and index < len(batches):
            time.sleep(sleep_seconds)

    payload = build_payload(previous, target_companies, fresh_quotes, failures)
    if dry_run:
        print("dry-run: data/market.json was not written")
        print(
            "market quotes fresh={fresh} retained_stale={stale} failures={failures} latest={latest}".format(
                fresh=len(fresh_quotes),
                stale=payload["stats"]["staleQuotesRetained"],
                failures=len(failures),
                latest=payload.get("latestTradingDate"),
            )
        )
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MARKET_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "market quotes fresh={fresh} retained_stale={stale} failures={failures} latest={latest}".format(
            fresh=len(fresh_quotes),
            stale=payload["stats"]["staleQuotesRetained"],
            failures=len(failures),
            latest=payload.get("latestTradingDate"),
        )
    )


if __name__ == "__main__":
    main()
