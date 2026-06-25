#!/usr/bin/env python3
"""Refresh the bundled JPX company universe from JPX's listed issues file.

The deployed app currently imports a hashed asset such as
assets/companyUniverse-*.js. This script replaces only the source company list in
that built file and keeps the rest of the bundle wrapper intact.
"""

from __future__ import annotations

import glob
import io
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"

JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"

EXCLUDE_PATTERNS = (
    "ETF",
    "ＥＴＦ",
    "ETN",
    "ＥＴＮ",
    "REIT",
    "リート",
    "投資法人",
    "上場投信",
    "投信",
    "指数連動",
    "インフラファンド",
)

EXCLUDE_MARKET_PATTERNS = (
    "ETF",
    "ＥＴＦ",
    "ETN",
    "ＥＴＮ",
    "ETF・ETN",
    "REIT",
    "ＲＥＩＴ",
    "不動産投信",
)


def find_column(columns: list[str], *needles: str) -> str:
    for col in columns:
        normalized = str(col)
        if all(needle in normalized for needle in needles):
            return col
    raise KeyError(f"Column containing {needles!r} was not found")


def js_string(value: str) -> str:
    return "`" + str(value).replace("\\", "\\\\").replace("`", "\\`") + "`"


def js_object(obj: dict) -> str:
    return (
        "{"
        + ",".join(
            [
                f"code:{js_string(obj['code'])}",
                f"name:{js_string(obj['name'])}",
                f"market:{js_string(obj['market'])}",
                f"industry:{js_string(obj['industry'])}",
            ]
        )
        + "}"
    )


def read_jpx_companies() -> tuple[list[dict[str, str]], str]:
    response = requests.get(JPX_URL, timeout=60)
    response.raise_for_status()

    table = pd.read_excel(io.BytesIO(response.content), dtype=str)
    columns = list(table.columns)
    code_col = find_column(columns, "コード")
    name_col = find_column(columns, "銘柄名")
    market_col = find_column(columns, "市場")
    industry_col = find_column(columns, "33業種")

    companies = []
    for _, row in table.iterrows():
        code = str(row.get(code_col, "")).strip()
        name = str(row.get(name_col, "")).strip()
        market = str(row.get(market_col, "")).strip()
        industry = str(row.get(industry_col, "")).strip()
        if not code or code.lower() == "nan" or not name or name.lower() == "nan":
            continue
        if any(token in market for token in EXCLUDE_MARKET_PATTERNS):
            continue
        if any(token in name for token in EXCLUDE_PATTERNS):
            continue
        if not re.fullmatch(r"\d{4}|\d{3}[A-Z]|\d{5}", code):
            continue
        companies.append(
            {
                "code": code,
                "name": name,
                "market": market if market and market.lower() != "nan" else "不明",
                "industry": industry if industry and industry.lower() != "nan" else "不明",
            }
        )

    return companies, datetime.now(timezone.utc).strftime("%Y%m%d")


def replace_bundle(companies: list[dict[str, str]], source_date: str) -> None:
    files = sorted(glob.glob(str(ASSETS_DIR / "companyUniverse-*.js")))
    if not files:
        raise FileNotFoundError("assets/companyUniverse-*.js was not found")
    path = Path(files[0])
    text = path.read_text(encoding="utf-8")

    source = {
        "source": "JPX 上場銘柄一覧",
        "sourceUrl": JPX_URL,
        "sourceDate": source_date,
        "companyCount": len(companies),
    }
    prefix = "var t="
    marker = ",n=e({companies"
    start = text.index(prefix) + len(prefix)
    end = text.index(marker, start)
    replacement = (
        "{"
        f"source:{js_string(source['source'])},"
        f"sourceUrl:{js_string(source['sourceUrl'])},"
        f"sourceDate:{js_string(source['sourceDate'])},"
        f"companyCount:{source['companyCount']},"
        "companies:["
        + ",".join(js_object(company) for company in companies)
        + "]}"
    )
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    print(f"updated {path} with {len(companies)} companies")


def main() -> None:
    companies, source_date = read_jpx_companies()
    replace_bundle(companies, source_date)


if __name__ == "__main__":
    main()
