#!/usr/bin/env python3
"""Refresh the domestic Prime/Standard/Growth company master from JPX."""

from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src/data/listedCompanies.json"
SOURCE_MODULE = ROOT / "src/lib/companySource.ts"
SOURCE_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/"
    "tvdivq0000001vg2-att/data_j.xls"
)
TARGET_MARKETS = ("プライム", "スタンダード", "グロース")


def download() -> bytes:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "KPI-Scope/1.0 (+https://github.com/ridyvk/gyyguuyfyt)"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def normalized_source_date(frame: pd.DataFrame) -> str:
    raw_values = frame["日付"].astype(str).str.replace(r"\.0$", "", regex=True)
    values = pd.to_datetime(raw_values, format="%Y%m%d", errors="coerce").dropna()
    if values.empty:
        raise ValueError("JPX workbook has no valid source date")
    return values.max().strftime("%Y%m%d")


def build_payload(frame: pd.DataFrame) -> dict:
    required = {"日付", "コード", "銘柄名", "市場・商品区分", "33業種区分"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"JPX workbook is missing columns: {sorted(missing)}")

    companies: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in frame.to_dict("records"):
        market_label = str(row["市場・商品区分"] or "").strip()
        if "内国株式" not in market_label:
            continue
        market = next(
            (candidate for candidate in TARGET_MARKETS if market_label.startswith(candidate)),
            None,
        )
        code = str(row["コード"] or "").strip().upper().removesuffix(".0")
        name = str(row["銘柄名"] or "").strip()
        industry = str(row["33業種区分"] or "").strip()
        if not market or len(code) != 4 or not name or not industry or code in seen:
            continue
        seen.add(code)
        companies.append(
            {
                "code": code,
                "name": name,
                "market": market,
                "industry": industry,
            }
        )

    companies.sort(key=lambda company: company["code"])
    if len(companies) < 3000:
        raise ValueError(f"JPX company count is unexpectedly low: {len(companies)}")
    return {
        "source": "JPX 上場銘柄一覧",
        "sourceUrl": SOURCE_URL,
        "sourceDate": normalized_source_date(frame),
        "companyCount": len(companies),
        "companies": companies,
    }


def main() -> int:
    frame = pd.read_excel(io.BytesIO(download()), dtype=str)
    frame.columns = [str(column).strip() for column in frame.columns]
    payload = build_payload(frame)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    SOURCE_MODULE.write_text(
        "export const listedCompanySource = {\n"
        "  name: 'JPX 上場銘柄一覧',\n"
        "  url: 'https://www.jpx.co.jp/markets/statistics-equities/misc/01.html',\n"
        f"  date: '{payload['sourceDate']}',\n"
        f"  count: {payload['companyCount']},\n"
        "} as const\n",
        encoding="utf-8",
    )
    print(
        f"Saved {payload['companyCount']} JPX companies "
        f"for {payload['sourceDate']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
