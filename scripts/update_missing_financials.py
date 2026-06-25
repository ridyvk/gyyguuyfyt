#!/usr/bin/env python3
"""Try to fill ordinary missing companies from EDINET annual securities reports.

This is intentionally conservative. It only adds records when it can find enough
annual XBRL facts to calculate at least a few comparable KPIs. Special financial
sectors, REITs, funds, and special securities are left for separate models.
"""

from __future__ import annotations

import io
import json
import os
import glob
import re
import time
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"
EDINET_BASE = "https://api.edinet-fsa.go.jp/api/v2"

ANNUAL_DOC_TYPE = "120"

EXCLUDED_INDUSTRIES = {
    "銀行業",
    "保険業",
    "証券、商品先物取引業",
    "その他金融業",
}

EXCLUDED_MARKET_PATTERNS = (
    "ETF",
    "ＥＴＦ",
    "ETN",
    "ＥＴＮ",
    "ETF・ETN",
    "ＲＥＩＴ",
    "REIT",
    "不動産投信",
)

EXCLUDED_NAME_PATTERNS = (
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
    "種類株式",
    "優先株",
    "社債型",
)

METRIC_TAGS = {
    "revenue": [
        "NetSales",
        "Revenue",
        "RevenueIFRS",
        "OperatingRevenue1",
        "OperatingRevenue2",
        "SalesRevenue",
    ],
    "operatingIncome": ["OperatingIncome", "OperatingProfit"],
    "netIncome": [
        "ProfitLossAttributableToOwnersOfParent",
        "ProfitLoss",
        "NetIncomeLoss",
    ],
    "totalAssets": ["Assets", "TotalAssets"],
    "equity": ["NetAssets", "Equity", "EquityAttributableToOwnersOfParent"],
    "operatingCashFlow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
    ],
    "inventories": ["Inventories"],
    "receivables": ["NotesAndAccountsReceivableTrade", "TradeAndOtherReceivables"],
    "cash": ["CashAndDeposits", "CashAndCashEquivalents"],
    "interestBearingDebt": [
        "InterestBearingDebt",
        "ShortTermBorrowings",
        "LongTermBorrowings",
        "BondsPayable",
    ],
    "eps": ["BasicEarningsLossPerShare", "BasicEarningsLossPerShareIFRS"],
    "bps": ["NetAssetsPerShare", "EquityAttributableToOwnersOfParentPerShare"],
}


def metric_value(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator * 100, 2)


def growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current / previous - 1) * 100, 2)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def context_bucket(context_ref: str | None) -> str | None:
    if not context_ref:
        return None
    ref = context_ref.lower()
    if "prioryear" in ref and "duration" in ref:
        return "previous_duration"
    if "prioryear" in ref and "instant" in ref:
        return "previous_instant"
    if ("currentyear" in ref or "current" in ref) and "duration" in ref:
        return "current_duration"
    if ("currentyear" in ref or "current" in ref) and "instant" in ref:
        return "current_instant"
    return None


def parse_xbrl(zip_bytes: bytes) -> dict[str, dict[str, float]]:
    facts: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.endswith(".xbrl") and "PublicDoc" in name
        ]
        if not names:
            names = [name for name in archive.namelist() if name.endswith(".xbrl")]
        for name in names[:3]:
            root = ET.fromstring(archive.read(name))
            for elem in root.iter():
                bucket = context_bucket(elem.attrib.get("contextRef"))
                if not bucket:
                    continue
                value = metric_value(elem.text)
                if value is None:
                    continue
                tag = local_name(elem.tag)
                for metric, tag_names in METRIC_TAGS.items():
                    if tag in tag_names:
                        facts[metric][bucket].append(value)

    picked: dict[str, dict[str, float]] = {}
    for metric, buckets in facts.items():
        picked[metric] = {}
        for bucket, values in buckets.items():
            if metric == "interestBearingDebt":
                picked[metric][bucket] = sum(values)
            else:
                picked[metric][bucket] = values[0]
    return picked


def build_record(company: dict, document: dict, facts: dict[str, dict[str, float]]) -> dict | None:
    cur_d = lambda key: facts.get(key, {}).get("current_duration")
    prv_d = lambda key: facts.get(key, {}).get("previous_duration")
    cur_i = lambda key: facts.get(key, {}).get("current_instant")
    prv_i = lambda key: facts.get(key, {}).get("previous_instant")

    revenue = cur_d("revenue")
    prev_revenue = prv_d("revenue")
    op_income = cur_d("operatingIncome")
    prev_op_income = prv_d("operatingIncome")
    net_income = cur_d("netIncome")
    prev_net_income = prv_d("netIncome")
    equity = cur_i("equity")
    prev_equity = prv_i("equity")
    assets = cur_i("totalAssets")
    operating_cf = cur_d("operatingCashFlow")

    metrics = {}

    def put(name: str, value: float | None, previous: float | None = None) -> None:
        if value is None:
            return
        metrics[name] = {"value": round(value, 2)}
        if previous is not None:
            metrics[name]["previousValue"] = round(previous, 2)

    put("revenueGrowth", growth(revenue, prev_revenue))
    put("operatingMargin", pct(op_income, revenue), pct(prev_op_income, prev_revenue))
    put("netMargin", pct(net_income, revenue), pct(prev_net_income, prev_revenue))
    put("roe", pct(net_income, equity), pct(prev_net_income, prev_equity))
    put("equityRatio", pct(equity, assets), pct(prev_equity, prv_i("totalAssets")))
    put("operatingCfMargin", pct(operating_cf, revenue), pct(prv_d("operatingCashFlow"), prev_revenue))
    put("inventoryGrowth", growth(cur_i("inventories"), prv_i("inventories")))
    put("receivablesGrowth", growth(cur_i("receivables"), prv_i("receivables")))

    debt = cur_i("interestBearingDebt")
    if debt is not None and equity:
        put("debtRatio", debt / equity)
    cash = cur_i("cash")
    if cash is not None or debt is not None:
        put("netCash", ((cash or 0) - (debt or 0)) / 100_000_000)

    if len(metrics) < 3:
        return None

    valuation = {}
    eps = cur_d("eps")
    bps = cur_i("bps")
    if eps is not None:
        valuation["eps"] = round(eps, 2)
    if bps is not None:
        valuation["bps"] = round(bps, 2)

    return {
        "code": company["code"],
        "companyName": company["name"],
        "documentId": document["docID"],
        "documentType": "AnnualSecuritiesReport",
        "filedAt": document.get("submitDateTime"),
        "periodEnd": document.get("periodEnd"),
        "periodType": "annual",
        "source": "EDINET",
        "sourceUrl": f"https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?{document['docID']}",
        "sourceDetail": "EDINET有価証券報告書XBRL・未取得普通企業の自動補完",
        "metrics": metrics,
        "history": [],
        "valuation": valuation,
        "quality": {
            "policy": "ordinary-missing-edinet-fallback",
            "autoFilled": True,
            "parserVersion": 1,
        },
    }


class EdinetClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()

    def _params(self, **params: str) -> dict[str, str]:
        return {**params, "Subscription-Key": self.api_key}

    def documents_for_date(self, target_date: date) -> list[dict]:
        url = f"{EDINET_BASE}/documents.json"
        response = self.session.get(
            url,
            params=self._params(date=target_date.isoformat(), type="2"),
            headers={"Ocp-Apim-Subscription-Key": self.api_key},
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def download_xbrl(self, doc_id: str) -> bytes:
        url = f"{EDINET_BASE}/documents/{doc_id}"
        response = self.session.get(
            url,
            params=self._params(type="1"),
            headers={"Ocp-Apim-Subscription-Key": self.api_key},
            timeout=90,
        )
        response.raise_for_status()
        return response.content


def load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def load_universe() -> dict[str, dict[str, str]]:
    files = sorted(glob.glob(str(ASSETS_DIR / "companyUniverse-*.js")))
    if not files:
        raise FileNotFoundError("assets/companyUniverse-*.js was not found")

    text = Path(files[0]).read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{code:`(?P<code>[^`]+)`,name:`(?P<name>[^`]+)`,market:`(?P<market>[^`]+)`,industry:`(?P<industry>[^`]+)`\}"
    )
    companies = [match.groupdict() for match in pattern.finditer(text)]
    return {
        company["code"]: company
        for company in companies
        if not is_security_like(company)
    }


def is_security_like(company: dict[str, str]) -> bool:
    code = company["code"]
    name = company["name"]
    market = company["market"]
    industry = company["industry"]

    if len(code) > 4 and not re.fullmatch(r"\d{3}[A-Z]", code):
        return True
    if any(token in market for token in EXCLUDED_MARKET_PATTERNS):
        return True
    if industry in EXCLUDED_INDUSTRIES:
        return True
    return any(token in name for token in EXCLUDED_NAME_PATTERNS)


def document_is_newer(document: dict, existing: dict | None) -> bool:
    if not existing:
        return True
    if document.get("docID") == existing.get("documentId"):
        return False
    submitted = str(document.get("submitDateTime") or document.get("submitDate") or "")
    existing_submitted = str(existing.get("filedAt") or "")
    return not existing_submitted or submitted > existing_submitted


def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY")
    if not api_key:
        print("EDINET_API_KEY is not set; skipping EDINET fill step")
        return

    financials_path = DATA_DIR / "financials.json"
    missing_path = DATA_DIR / "missing-companies.json"
    financials = load_json(financials_path, {"records": {}})
    missing = load_json(missing_path, {"reasons": {}})
    universe = load_universe()
    ordinary = missing.get("reasons", {}).get("ordinary-company", [])

    records = financials.setdefault("records", {})
    target_by_code = {item["code"]: item for item in ordinary if item["code"] not in records}

    lookback_days = int(os.environ.get("EDINET_LOOKBACK_DAYS", "540"))
    refresh_days = int(os.environ.get("EDINET_REFRESH_DAYS", "90"))
    days = max(lookback_days, refresh_days)
    limit = int(os.environ.get("EDINET_FILL_LIMIT", "80"))
    client = EdinetClient(api_key)
    added = 0
    refreshed = 0
    failures = 0

    for offset in range(days):
        day = date.today() - timedelta(days=offset)
        try:
            documents = client.documents_for_date(day)
        except Exception as exc:
            print(f"documents fetch failed for {day}: {exc}")
            continue

        for doc in documents:
            code = str(doc.get("secCode") or "")[:4]
            if code not in universe:
                continue
            if str(doc.get("docTypeCode")) != ANNUAL_DOC_TYPE:
                continue
            existing = records.get(code)
            is_missing_target = code in target_by_code
            is_recent_refresh = offset < refresh_days and document_is_newer(doc, existing)
            if not is_missing_target and not is_recent_refresh:
                continue
            try:
                zip_bytes = client.download_xbrl(doc["docID"])
                facts = parse_xbrl(zip_bytes)
                record = build_record(universe[code], doc, facts)
            except Exception as exc:
                print(f"{code} {doc.get('docID')} failed: {exc}")
                failures += 1
                continue
            if not record:
                continue

            if is_recent_refresh and not is_missing_target:
                record["quality"]["policy"] = "ordinary-edinet-latest-refresh"
                refreshed += 1
                print(f"refreshed {code} {record['companyName']}")
            else:
                added += 1
                print(f"added {code} {record['companyName']}")

            records[code] = record
            target_by_code.pop(code, None)
            time.sleep(0.4)
            if added + refreshed >= limit:
                break
        if added + refreshed >= limit:
            break
        time.sleep(0.2)

    financials["generatedAt"] = datetime.now(timezone.utc).isoformat()
    financials.setdefault("stats", {})["companies"] = len(records)
    financials.setdefault("stats", {})["ordinaryFallbackAdded"] = (
        financials.get("stats", {}).get("ordinaryFallbackAdded", 0) + added
    )
    financials.setdefault("stats", {})["ordinaryLatestRefreshed"] = (
        financials.get("stats", {}).get("ordinaryLatestRefreshed", 0) + refreshed
    )
    financials.setdefault("stats", {})["ordinaryRefreshFailures"] = (
        financials.get("stats", {}).get("ordinaryRefreshFailures", 0) + failures
    )
    financials_path.write_text(
        json.dumps(financials, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "ordinary fallback added={added} refreshed={refreshed} "
        "remaining_missing={remaining} failures={failures}".format(
            added=added,
            refreshed=refreshed,
            remaining=len(target_by_code),
            failures=failures,
        )
    )


if __name__ == "__main__":
    main()
