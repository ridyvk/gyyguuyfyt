#!/usr/bin/env python3
"""Update KPI Scope's daily market snapshot from J-Quants API v2."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://api.jquants.com/v2"
SNAPSHOT = Path(__file__).resolve().parents[1] / "public/data/market.json"


def number(value: object) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def get_json(
    path: str,
    api_key: str,
    params: dict[str, str],
    retries: int = 4,
) -> dict:
    query = dict(params)
    all_data: list[dict] = []
    while True:
        url = f"{API}{path}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(
            url,
            headers={
                "x-api-key": api_key,
                "User-Agent": "KPI-Scope/1.0",
            },
        )
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    payload = json.loads(response.read())
                break
            except urllib.error.HTTPError as error:
                if error.code in {400, 403, 404}:
                    raise
                if attempt == retries - 1:
                    raise
                time.sleep(2**attempt)
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(2**attempt)
        all_data.extend(payload.get("data", []))
        pagination_key = payload.get("pagination_key")
        if not pagination_key:
            return {"data": all_data}
        query["pagination_key"] = pagination_key


def load_snapshot() -> dict:
    if not SNAPSHOT.exists():
        return {}
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def search_start(snapshot: dict) -> date:
    latest = snapshot.get("latestTradingDate")
    if not latest:
        return datetime.now(timezone.utc).date()
    try:
        observed_delay = (
            datetime.now(timezone.utc).date() - date.fromisoformat(latest)
        ).days
    except ValueError:
        return datetime.now(timezone.utc).date()
    return datetime.now(timezone.utc).date() - timedelta(
        days=max(observed_delay - 3, 0)
    )


def fetch_trading_days(
    api_key: str,
    snapshot: dict,
    max_lookback_days: int,
) -> list[tuple[str, list[dict]]]:
    trading_days: list[tuple[str, list[dict]]] = []
    start = search_start(snapshot)
    for offset in range(max_lookback_days):
        target = start - timedelta(days=offset)
        try:
            payload = get_json(
                "/equities/bars/daily",
                api_key,
                {"date": target.isoformat()},
            )
        except urllib.error.HTTPError as error:
            if error.code in {400, 403, 404}:
                continue
            raise
        rows = payload.get("data", [])
        if rows:
            trading_days.append((target.isoformat(), rows))
        if len(trading_days) == 2:
            return trading_days
    return trading_days


def build_quotes(trading_days: list[tuple[str, list[dict]]]) -> dict[str, dict]:
    if not trading_days:
        return {}
    latest_date, latest_rows = trading_days[0]
    previous_rows = trading_days[1][1] if len(trading_days) > 1 else []
    previous_by_code = {
        str(row.get("Code") or "")[:4]: row for row in previous_rows
    }
    quotes: dict[str, dict] = {}
    for row in latest_rows:
        code = str(row.get("Code") or "")[:4]
        close = number(row.get("C"))
        if len(code) != 4 or close is None or close <= 0:
            continue
        previous_close = number(previous_by_code.get(code, {}).get("C"))
        quote = {
            "date": str(row.get("Date") or latest_date),
            "close": round(close, 4),
            "volume": number(row.get("Vo")),
            "source": "J-Quants",
        }
        if previous_close is not None and previous_close > 0:
            quote["previousClose"] = round(previous_close, 4)
            quote["changePercent"] = round(
                (close / previous_close - 1) * 100,
                4,
            )
        quotes[code] = quote
    return quotes


def update_fundamentals(
    api_key: str,
    snapshot: dict,
    lookback_days: int,
    bootstrap_days: int,
) -> dict[str, dict]:
    fundamentals = dict(snapshot.get("fundamentals", {}))
    days = lookback_days if fundamentals else bootstrap_days
    today = datetime.now(timezone.utc).date()
    for offset in range(days):
        target = today - timedelta(days=offset)
        try:
            rows = get_json(
                "/fins/summary",
                api_key,
                {"date": target.isoformat()},
            ).get("data", [])
        except urllib.error.HTTPError as error:
            if error.code in {400, 403, 404}:
                continue
            raise
        for row in rows:
            code = str(row.get("Code") or "")[:4]
            if len(code) != 4:
                continue
            disclosed_date = str(row.get("DiscDate") or target.isoformat())
            disclosed_at = f"{disclosed_date} {row.get('DiscTime') or ''}".strip()
            current = fundamentals.get(code, {})
            if disclosed_at < str(current.get("disclosedAt") or ""):
                continue
            eps = number(row.get("EPS")) or number(row.get("NCEPS"))
            forecast_eps = number(row.get("FEPS")) or number(row.get("FNCEPS"))
            bps = number(row.get("BPS")) or number(row.get("NCBPS"))
            basis = {
                "disclosedDate": disclosed_date,
                "disclosedAt": disclosed_at,
            }
            if eps is not None:
                basis["eps"] = round(eps, 4)
            if forecast_eps is not None:
                basis["forecastEps"] = round(forecast_eps, 4)
            if bps is not None:
                basis["bps"] = round(bps, 4)
            if len(basis) > 2:
                fundamentals[code] = basis
        if offset and offset % 50 == 0:
            print(f"Scanned {offset}/{days} financial disclosure days")
        time.sleep(0.04)
    return fundamentals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-lookback-days", type=int, default=120)
    parser.add_argument("--financial-lookback-days", type=int, default=7)
    parser.add_argument("--financial-bootstrap-days", type=int, default=460)
    args = parser.parse_args()
    api_key = os.environ.get("JQUANTS_API_KEY", "").strip()
    if not api_key:
        print("JQUANTS_API_KEY is not configured.", file=sys.stderr)
        return 2

    snapshot = load_snapshot()
    trading_days = fetch_trading_days(
        api_key,
        snapshot,
        args.max_lookback_days,
    )
    quotes = build_quotes(trading_days)
    if not quotes:
        raise RuntimeError(
            "No accessible daily quote was found. Check the API key and plan delay."
        )

    fundamentals = update_fundamentals(
        api_key,
        snapshot,
        args.financial_lookback_days,
        args.financial_bootstrap_days,
    )
    trading_dates = [trading_date for trading_date, _ in trading_days]
    snapshot = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "source": "J-Quants",
        "status": "ready",
        "message": "J-Quantsの日足終値を自動更新しています。配信遅延は契約プランに従います。",
        "latestTradingDate": trading_dates[0],
        "quotes": quotes,
        "fundamentals": fundamentals,
        "stats": {
            "companies": len(quotes),
            "tradingDates": trading_dates,
            "fundamentals": len(fundamentals),
        },
    }
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(quotes)} quotes for {trading_dates[0]} "
        f"and {len(fundamentals)} valuation records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
