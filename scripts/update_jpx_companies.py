#!/usr/bin/env python3
"""Refresh the domestic Prime/Standard/Growth company master from JPX."""

from __future__ import annotations

import io
import json
import re
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src/data/listedCompanies.json"
SOURCE_MODULE = ROOT / "src/lib/companySource.ts"
SOURCE_PAGE_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
FALLBACK_SOURCE_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/"
    "tvdivq0000001vg2-att/data_j.xlsx"
)
TARGET_MARKETS = ("プライム", "スタンダード", "グロース")
WORKBOOK_LINK = re.compile(
    r'href=["\']([^"\']*tvdivq0000001vg2-att/data_j\.xlsx?[^"\']*)["\']',
    re.IGNORECASE,
)


def request_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "KPI-Scope/1.0 (+https://github.com/ridyvk/gyyguuyfyt)"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def discover_source_url(page_html: str) -> str:
    """Resolve the current workbook URL from JPX's stable index page."""
    match = WORKBOOK_LINK.search(page_html)
    if not match:
        raise ValueError("JPX company-list workbook link was not found")
    return urljoin(SOURCE_PAGE_URL, unescape(match.group(1)))


def download() -> tuple[str, bytes]:
    """Download the current workbook, retaining a known-good direct fallback."""
    source_url = FALLBACK_SOURCE_URL
    try:
        page_html = request_bytes(SOURCE_PAGE_URL).decode("utf-8", errors="replace")
        source_url = discover_source_url(page_html)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"warning: JPX workbook discovery failed: {error}")

    try:
        return source_url, request_bytes(source_url)
    except OSError:
        if source_url == FALLBACK_SOURCE_URL:
            raise
        return FALLBACK_SOURCE_URL, request_bytes(FALLBACK_SOURCE_URL)


def normalized_source_date(frame: pd.DataFrame) -> str:
    raw_values = frame["日付"].astype(str).str.replace(r"\.0$", "", regex=True)
    values = pd.to_datetime(raw_values, format="%Y%m%d", errors="coerce").dropna()
    if values.empty:
        raise ValueError("JPX workbook has no valid source date")
    return values.max().strftime("%Y%m%d")


def build_payload(frame: pd.DataFrame, source_url: str = FALLBACK_SOURCE_URL) -> dict:
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
        "sourceUrl": source_url,
        "sourceDate": normalized_source_date(frame),
        "companyCount": len(companies),
        "companies": companies,
    }


def main() -> int:
    source_url, workbook = download()
    frame = pd.read_excel(io.BytesIO(workbook), dtype=str)
    frame.columns = [str(column).strip() for column in frame.columns]
    payload = build_payload(frame, source_url)
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
