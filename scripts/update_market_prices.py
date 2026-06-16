#!/usr/bin/env python3
"""Update KPI Scope's daily market snapshot without an API key.

Prices are read from Yahoo Finance's public chart endpoint. EPS/BPS are
provided by the EDINET/TDnet financial snapshot, so no user-side stock data
account or secret is required.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[1] / "public/data/market.json"
FINANCIALS = Path(__file__).resolve().parents[1] / "public/data/financials.json"
COMPANY_MASTER = (
    Path(__file__).resolve().parents[1] / "src/data/listedCompanies.json"
)
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
JST = timezone(timedelta(hours=9))


def number(value: object) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def get_json(url: str, retries: int = 4) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; KPI-Scope/1.0; "
                "+https://github.com/ridyvk/gyyguuyfyt)"
            ),
        },
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(0.7 * (attempt + 1))
    raise RuntimeError("request failed")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def company_codes() -> list[str]:
    financials = load_json(FINANCIALS)
    records = financials.get("records", {})
    if records:
        return sorted(str(code) for code in records)
    master = load_json(COMPANY_MASTER)
    return sorted(str(company["code"]) for company in master.get("companies", []))


def valuation_fundamentals() -> dict[str, dict]:
    financials = load_json(FINANCIALS)
    fundamentals: dict[str, dict] = {}
    for code, record in financials.get("records", {}).items():
        valuation = dict(record.get("valuation") or {})
        if not valuation:
            continue
        valuation.setdefault("disclosedDate", record.get("periodEnd"))
        valuation.setdefault("disclosedAt", record.get("filedAt"))
        fundamentals[str(code)] = valuation
    return fundamentals


def fetch_quote(code: str) -> tuple[str, dict]:
    symbol = f"{code}.T"
    url = YAHOO_CHART.format(symbol=urllib.parse.quote(symbol)) + (
        "?range=7d&interval=1d"
    )
    payload = get_json(url)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(payload.get("chart", {}).get("error") or "no result")
    meta = result.get("meta", {})
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    timestamps = result.get("timestamp") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    points = [
        (timestamp, number(close), number(volume))
        for timestamp, close, volume in zip(timestamps, closes, volumes)
        if number(close) is not None and number(close) > 0
    ]
    if not points:
        close = number(meta.get("regularMarketPrice"))
        if close is None or close <= 0:
            raise RuntimeError("close price not found")
        timestamp = int(meta.get("regularMarketTime") or time.time())
        points = [(timestamp, close, number(meta.get("regularMarketVolume")))]

    latest_time, close, volume = points[-1]
    previous_close = points[-2][1] if len(points) > 1 else number(
        meta.get("chartPreviousClose")
    )
    quote_payload = {
        "date": datetime.fromtimestamp(int(latest_time), JST)
        .date()
        .isoformat(),
        "close": round(float(close), 4),
        "volume": volume,
        "source": "Yahoo Finance",
    }
    if previous_close is not None and previous_close > 0:
        quote_payload["previousClose"] = round(float(previous_close), 4)
        quote_payload["changePercent"] = round(
            (float(close) / float(previous_close) - 1) * 100,
            4,
        )
    return code, quote_payload


def fetch_quotes(codes: list[str], workers: int) -> tuple[dict[str, dict], list[str]]:
    quotes: dict[str, dict] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_by_code = {
            executor.submit(fetch_quote, code): code for code in codes
        }
        for index, future in enumerate(as_completed(future_by_code), 1):
            code = future_by_code[future]
            try:
                result_code, quote = future.result()
                quotes[result_code] = quote
            except Exception as error:
                failures.append(f"{code}: {error}")
            if index % 250 == 0:
                print(f"Fetched {index}/{len(codes)} market quotes")
    return quotes, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--max-companies", type=int, default=4500)
    args = parser.parse_args()

    previous_snapshot = load_json(SNAPSHOT)
    codes = company_codes()[: args.max_companies]
    quotes, failures = fetch_quotes(codes, max(1, args.max_workers))
    if not quotes:
        raise RuntimeError("No market quote was fetched.")

    merged_quotes = {
        **previous_snapshot.get("quotes", {}),
        **quotes,
    }
    fundamentals = valuation_fundamentals()
    latest_dates = sorted(
        {quote["date"] for quote in merged_quotes.values() if quote.get("date")},
        reverse=True,
    )
    snapshot = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "source": "Yahoo Finance",
        "status": "ready",
        "message": (
            "Yahoo Financeの日足終値とEDINET・TDnetのEPS/BPSから"
            "PER・PBRを自動計算しています。"
        ),
        "latestTradingDate": latest_dates[0] if latest_dates else None,
        "quotes": merged_quotes,
        "fundamentals": fundamentals,
        "stats": {
            "companies": len(merged_quotes),
            "tradingDates": latest_dates[:5],
            "fundamentals": len(fundamentals),
            "quoteFailures": len(failures),
        },
    }
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(merged_quotes)} quotes and "
        f"{len(fundamentals)} valuation records."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
