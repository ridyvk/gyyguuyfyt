#!/usr/bin/env python3
"""Update KPI Scope's market snapshot without an API key.

Prices are read from Yahoo Finance's public chart endpoint. The updater fetches
quotes for the listed-company universe, while PER/PBR are calculated only when
EPS/BPS are available from the financial snapshot.
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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from data_quality import is_iso_date, normalize_security_code

SNAPSHOT = Path(__file__).resolve().parents[1] / "public/data/market.json"
FINANCIALS = Path(__file__).resolve().parents[1] / "public/data/financials.json"
COMPANY_MASTER = (
    Path(__file__).resolve().parents[1] / "src/data/listedCompanies.json"
)
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
JST = timezone(timedelta(hours=9))
MAX_FALLBACK_QUOTE_AGE_DAYS = 10
INTRADAY_RANGE = "5d"
INTRADAY_INTERVAL = "15m"
DAILY_RANGE = "7d"
DAILY_INTERVAL = "1d"


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


def chart_url(symbol: str, range_: str, interval: str) -> str:
    query = urllib.parse.urlencode({"range": range_, "interval": interval})
    return f"{YAHOO_CHART.format(symbol=urllib.parse.quote(symbol))}?{query}"


def chart_result(symbol: str, range_: str, interval: str) -> dict:
    payload = get_json(chart_url(symbol, range_, interval))
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(payload.get("chart", {}).get("error") or "no result")
    return result


def valid_chart_points(result: dict) -> list[tuple[int, float, float | None]]:
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    timestamps = result.get("timestamp") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    return [
        (int(timestamp), float(close), number(volume))
        for timestamp, close, volume in zip(timestamps, closes, volumes)
        if number(close) is not None and number(close) > 0
    ]


def fallback_session_volume(
    points: list[tuple[int, float, float | None]],
    latest_time: int,
    interval: str,
) -> float | None:
    if not points:
        return None
    if interval == DAILY_INTERVAL:
        return points[-1][2]

    latest_date = datetime.fromtimestamp(latest_time, JST).date()
    session_volumes = [
        volume
        for timestamp, _, volume in points
        if volume is not None
        and volume >= 0
        and datetime.fromtimestamp(timestamp, JST).date() == latest_date
    ]
    return sum(session_volumes) if session_volumes else None


def quote_payload_from_chart_result(result: dict, interval: str) -> dict:
    meta = result.get("meta", {})
    points = valid_chart_points(result)
    meta_price = number(meta.get("regularMarketPrice"))
    meta_time = int(meta.get("regularMarketTime") or 0)
    meta_volume = number(meta.get("regularMarketVolume"))

    if points:
        latest_time, close, volume = points[-1]
        previous_close = number(meta.get("chartPreviousClose"))
        if previous_close is None and interval == DAILY_INTERVAL and len(points) > 1:
            previous_close = points[-2][1]
        price_type = (
            f"intraday-{interval}"
            if interval != DAILY_INTERVAL
            else "daily-close"
        )
        use_meta_price = (
            meta_price is not None
            and meta_price > 0
            and (
                meta_time > latest_time
                or (interval == DAILY_INTERVAL and meta_time >= latest_time)
            )
        )
        if use_meta_price:
            latest_time, close, volume = (
                meta_time,
                meta_price,
                meta_volume if meta_volume is not None else volume,
            )
            price_type = "regular-market-price"
    else:
        if meta_price is None or meta_price <= 0:
            raise RuntimeError("close price not found")
        latest_time, close, volume = meta_time or int(time.time()), meta_price, meta_volume
        previous_close = number(meta.get("chartPreviousClose"))
        price_type = "regular-market-price"

    if meta_volume is not None and meta_volume > 0:
        volume = meta_volume
    elif points:
        volume = fallback_session_volume(points, latest_time, interval)

    timestamp_jst = datetime.fromtimestamp(int(latest_time), JST)
    quote_payload = {
        "date": timestamp_jst.date().isoformat(),
        "timestamp": timestamp_jst.isoformat(),
        "close": round(float(close), 4),
        "volume": volume,
        "source": "Yahoo Finance",
        "priceType": price_type,
        "quoteInterval": interval,
        "isRealtime": False,
    }
    if previous_close is not None and previous_close > 0:
        quote_payload["previousClose"] = round(float(previous_close), 4)
        quote_payload["changePercent"] = round(
            (float(close) / float(previous_close) - 1) * 100,
            4,
        )
    return quote_payload


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def company_codes() -> list[str]:
    """Return the quote universe.

    Quotes should not be limited to financial records. A stock can have a latest
    price even when EPS/BPS are still missing, so the listed-company master is
    the primary source. Financial records are used only as a fallback.
    """
    master = load_json(COMPANY_MASTER)
    master_codes = sorted(
        str(company["code"])
        for company in master.get("companies", [])
        if normalize_security_code(company.get("code")) == str(company.get("code") or "")
    )
    if master_codes:
        return master_codes
    financials = load_json(FINANCIALS)
    return sorted(str(code) for code in financials.get("records", {}))


def valuation_fundamentals() -> dict[str, dict]:
    financials = load_json(FINANCIALS)
    fundamentals: dict[str, dict] = {}
    for code, record in financials.get("records", {}).items():
        valuation = dict(record.get("valuation") or {})
        if not valuation:
            continue
        valuation.setdefault("disclosedDate", record.get("periodEnd"))
        valuation.setdefault("disclosedAt", record.get("filedAt"))
        valuation.setdefault("financialSource", record.get("source"))
        valuation.setdefault("financialDocumentType", record.get("documentType"))
        fundamentals[str(code)] = valuation
    return fundamentals


def fetch_quote(code: str) -> tuple[str, dict]:
    symbol = f"{code}.T"
    try:
        result = chart_result(symbol, INTRADAY_RANGE, INTRADAY_INTERVAL)
        return code, quote_payload_from_chart_result(result, INTRADAY_INTERVAL)
    except Exception as intraday_error:
        try:
            result = chart_result(symbol, DAILY_RANGE, DAILY_INTERVAL)
            return code, quote_payload_from_chart_result(result, DAILY_INTERVAL)
        except Exception as daily_error:
            raise RuntimeError(
                f"intraday failed: {intraday_error}; daily failed: {daily_error}"
            ) from daily_error


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


def merge_quotes(
    codes: list[str],
    previous_quotes: dict,
    fresh_quotes: dict,
    today: date,
) -> tuple[dict[str, dict], int, int]:
    merged: dict[str, dict] = {}
    fallback_count = 0
    stale_dropped = 0
    for code in codes:
        if code in fresh_quotes:
            merged[code] = {**fresh_quotes[code], "stale": False}
            continue
        previous = previous_quotes.get(code)
        quote_date = str((previous or {}).get("date") or "")
        if not isinstance(previous, dict) or not is_iso_date(quote_date):
            stale_dropped += 1
            continue
        if (today - date.fromisoformat(quote_date)).days > MAX_FALLBACK_QUOTE_AGE_DAYS:
            stale_dropped += 1
            continue
        merged[code] = {**previous, "stale": True}
        fallback_count += 1
    return merged, fallback_count, stale_dropped


def mark_market_date_staleness(
    quotes: dict[str, dict],
) -> tuple[str | None, int]:
    """Mark successfully fetched but old exchange dates as stale."""
    latest = max(
        (
            str(quote.get("date") or "")
            for quote in quotes.values()
            if is_iso_date(quote.get("date"))
        ),
        default=None,
    )
    if latest is None:
        return None, 0

    stale = 0
    for quote in quotes.values():
        quote_date = str(quote.get("date") or "")
        market_date_stale = is_iso_date(quote_date) and quote_date < latest
        quote["stale"] = bool(quote.get("stale")) or market_date_stale
        if market_date_stale:
            stale += 1
    return latest, stale


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

    merged_quotes, fallback_quotes, stale_quotes_dropped = merge_quotes(
        codes,
        previous_snapshot.get("quotes", {}),
        quotes,
        datetime.now(JST).date(),
    )
    latest_trading_date, market_date_stale_quotes = mark_market_date_staleness(
        merged_quotes
    )
    fundamentals = valuation_fundamentals()
    latest_dates = sorted(
        {quote["date"] for quote in merged_quotes.values() if quote.get("date")},
        reverse=True,
    )
    latest_timestamps = sorted(
        {
            quote["timestamp"]
            for quote in merged_quotes.values()
            if quote.get("timestamp")
        },
        reverse=True,
    )
    snapshot = {
        "schemaVersion": 3,
        "generatedAt": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "source": "Yahoo Finance",
        "status": "partial" if failures else "ready",
        "message": (
            "Yahoo Financeの公開株価データとEDINET・TDnetのEPS/BPSから"
            "PER・PBRを自動計算しています。株価はリアルタイム保証ではありません。"
        ),
        "latestTradingDate": latest_trading_date,
        "latestQuoteTimestamp": latest_timestamps[0] if latest_timestamps else None,
        "quotes": merged_quotes,
        "fundamentals": fundamentals,
        "stats": {
            "quoteUniverse": len(codes),
            "companies": len(merged_quotes),
            "tradingDates": latest_dates[:5],
            "fundamentals": len(fundamentals),
            "quoteFailures": len(failures),
            "freshQuotesFetched": len(quotes),
            "fallbackQuotes": fallback_quotes,
            "staleQuotesDropped": stale_quotes_dropped,
            "marketDateStaleQuotes": market_date_stale_quotes,
            "maxFallbackQuoteAgeDays": MAX_FALLBACK_QUOTE_AGE_DAYS,
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
