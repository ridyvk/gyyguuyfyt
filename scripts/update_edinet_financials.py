#!/usr/bin/env python3
"""Update KPI Scope's normalized financial snapshot from EDINET XBRL."""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://api.edinet-fsa.go.jp/api/v2"
SNAPSHOT = Path(__file__).resolve().parents[1] / "public/data/financials.json"
COMPANY_MASTER = Path(__file__).resolve().parents[1] / "src/data/listedCompanies.json"
SNAPSHOT_SCHEMA_VERSION = 2

FACT_NAMES = {
    "revenue": (
        "NetSales",
        "Revenue",
        "RevenueIFRS",
        "RevenueFromContractsWithCustomers",
        "RevenueFromContractsWithCustomersIFRS",
        "OperatingRevenue1",
        "OperatingRevenue2",
        "GrossOperatingRevenue",
        "OrdinaryIncome",
    ),
    "operatingIncome": (
        "OperatingIncome",
        "OperatingProfitLoss",
        "OperatingProfitLossIFRS",
    ),
    "profit": (
        "ProfitLossAttributableToOwnersOfParent",
        "ProfitLossAttributableToOwnersOfParentIFRS",
        "ProfitLoss",
        "ProfitLossIFRS",
        "NetIncomeLoss",
        "NetIncome",
    ),
    "operatingCf": (
        "NetCashProvidedByUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivitiesIFRS",
    ),
    "equity": (
        "EquityAttributableToOwnersOfParent",
        "EquityAttributableToOwnersOfParentIFRS",
        "Equity",
        "EquityIFRS",
        "ShareholdersEquity",
        "NetAssets",
    ),
    "assets": ("Assets", "AssetsIFRS", "TotalAssets"),
    "cash": (
        "CashAndCashEquivalents",
        "CashAndCashEquivalentsIFRS",
        "CashAndDeposits",
    ),
    "inventory": (
        "Inventories",
        "InventoriesIFRS",
        "MerchandiseAndFinishedGoods",
    ),
    "receivables": (
        "NotesAndAccountsReceivableTradeAndContractAssets",
        "NotesAndAccountsReceivableTrade",
        "AccountsReceivableTrade",
        "TradeAndOtherReceivablesCurrent",
        "TradeAndOtherReceivablesCurrentIFRS",
    ),
    "debt": (
        "InterestBearingDebt",
        "InterestBearingLiabilities",
        "BondsAndBorrowings",
    ),
}
DEBT_COMPONENTS = (
    "ShortTermLoansPayable",
    "CurrentPortionOfLongTermLoansPayable",
    "CurrentPortionOfBonds",
    "BondsPayable",
    "LongTermLoansPayable",
    "LeaseLiabilitiesCurrent",
    "LeaseLiabilitiesNoncurrent",
    "BorrowingsCurrent",
    "BorrowingsCurrentIFRS",
    "BorrowingsNoncurrent",
    "BorrowingsNoncurrentIFRS",
)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def number(text: str | None) -> float | None:
    if not text:
        return None
    value = text.strip().replace(",", "").replace("△", "-").replace("▲", "-")
    if not value or value in {"-", "－", "―", "–"}:
        return None
    if value.startswith("(") and value.endswith(")"):
        value = f"-{value[1:-1]}"
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except ValueError:
        return None


def get(url: str, api_key: str, retries: int = 4) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Ocp-Apim-Subscription-Key": api_key,
            "User-Agent": "KPI-Scope/1.0",
        },
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("request failed")


def list_filings(api_key: str, days: int) -> tuple[dict[str, dict], int]:
    latest: dict[str, dict] = {}
    scanned = 0
    today = datetime.now(timezone.utc).date()
    for offset in range(days):
        target = today - timedelta(days=offset)
        query = urllib.parse.urlencode({"date": target.isoformat(), "type": 2})
        payload = json.loads(get(f"{API}/documents.json?{query}", api_key))
        status = str(payload.get("metadata", {}).get("status", "200"))
        if status != "200":
            raise RuntimeError(payload.get("metadata", {}).get("message", status))
        results = payload.get("results", [])
        scanned += len(results)
        for item in results:
            description = str(item.get("docDescription") or "")
            if not (
                item.get("secCode")
                and str(item.get("xbrlFlag")) == "1"
                and str(item.get("docTypeCode")) in {"120", "130"}
                and "有価証券報告書" in description
            ):
                continue
            code = str(item["secCode"])[:4]
            if str(item.get("submitDateTime") or "") > str(
                latest.get(code, {}).get("submitDateTime") or ""
            ):
                latest[code] = item
    return latest, scanned


def xbrl_from_zip(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".xbrl")
            and "publicdoc" in name.lower()
            and "audit" not in name.lower()
        ]
        if not names:
            names = [name for name in archive.namelist() if name.lower().endswith(".xbrl")]
        if not names:
            raise ValueError("XBRL instance not found")
        return archive.read(sorted(names, key=lambda name: (name.count("/"), len(name)))[0])


def parse_xbrl(data: bytes) -> tuple[dict, dict]:
    root = ET.fromstring(data)
    contexts: dict[str, dict] = {}
    facts: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for element in root.iter():
        if local_name(element.tag) != "context" or not element.attrib.get("id"):
            continue
        context = {"start": None, "end": None, "instant": None, "dimensions": []}
        for child in element.iter():
            name, text = local_name(child.tag), (child.text or "").strip()
            if name in {"startDate", "endDate", "instant"}:
                context[{"startDate": "start", "endDate": "end", "instant": "instant"}[name]] = text
            elif name in {"explicitMember", "typedMember"}:
                context["dimensions"].append(text or "typedMember")
        contexts[element.attrib["id"]] = context
    for element in root.iter():
        context_id = element.attrib.get("contextRef")
        value = number(element.text)
        if context_id in contexts and value is not None:
            facts[local_name(element.tag)].append((context_id, value))
    return contexts, facts


def is_consolidated(context_id: str, context: dict) -> bool:
    text = context_id + " " + " ".join(context["dimensions"])
    return "NonConsolidated" not in text


def rank(context_id: str, context: dict, period_end: str) -> int:
    text = context_id + " " + " ".join(context["dimensions"])
    return (
        (30 if (context["instant"] or context["end"]) == period_end else 0)
        + (20 if "ConsolidatedMember" in text else 0)
        + (12 if not context["dimensions"] else 0)
        + (8 if "CurrentYear" in context_id else 0)
    )


def values_for(
    contexts: dict,
    facts: dict,
    names: tuple[str, ...],
    duration: bool,
) -> dict[str, float]:
    source = [fact for name in names for fact in facts.get(name, [])]
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for context_id, value in source:
        context = contexts[context_id]
        period_end = context["end"] if duration else context["instant"]
        if not period_end or not is_consolidated(context_id, context):
            continue
        if duration:
            try:
                days = (date.fromisoformat(context["end"]) - date.fromisoformat(context["start"])).days
            except (TypeError, ValueError):
                continue
            if not 250 <= days <= 460:
                continue
        grouped[period_end].append((context_id, value))
    return {
        period_end: max(
            candidates,
            key=lambda candidate: rank(candidate[0], contexts[candidate[0]], period_end),
        )[1]
        for period_end, candidates in grouped.items()
    }


def previous(values: dict[str, float], period_end: str) -> float | None:
    candidates = [(key, value) for key, value in values.items() if key < period_end]
    return max(candidates, default=(None, None))[1]


def at(values: dict[str, float], period_end: str) -> float | None:
    if period_end in values:
        return values[period_end]
    candidates = [(key, value) for key, value in values.items() if key <= period_end]
    return max(candidates, default=(None, None))[1]


def percent(top: float | None, bottom: float | None) -> float | None:
    return None if top is None or bottom is None or bottom <= 0 else top / bottom * 100


def growth(current: float | None, prior: float | None) -> float | None:
    return None if current is None or prior is None or prior <= 0 else (current / prior - 1) * 100


def add_metric(metrics: dict, key: str, value: float | None, prior: float | None = None) -> None:
    if value is None or not math.isfinite(value):
        return
    metrics[key] = {"value": round(value, 2)}
    if prior is not None and math.isfinite(prior):
        metrics[key]["previousValue"] = round(prior, 2)


def build_record(filing: dict, data: bytes) -> dict:
    contexts, facts = parse_xbrl(data)
    period_end = str(filing["periodEnd"])
    series = {
        key: values_for(
            contexts,
            facts,
            names,
            key in {"revenue", "operatingIncome", "profit", "operatingCf"},
        )
        for key, names in FACT_NAMES.items()
    }
    if not series["debt"]:
        debt: dict[str, float] = defaultdict(float)
        for name in DEBT_COMPONENTS:
            for key, value in values_for(contexts, facts, (name,), False).items():
                debt[key] += value
        series["debt"] = dict(debt)

    current = {key: at(values, period_end) for key, values in series.items()}
    prior = {key: previous(values, period_end) for key, values in series.items()}
    average_equity = (
        (current["equity"] + prior["equity"]) / 2
        if current["equity"] is not None and prior["equity"] is not None
        else current["equity"]
    )
    metrics: dict[str, dict] = {}
    add_metric(metrics, "revenueGrowth", growth(current["revenue"], prior["revenue"]))
    add_metric(
        metrics,
        "operatingMargin",
        percent(current["operatingIncome"], current["revenue"]),
        percent(prior["operatingIncome"], prior["revenue"]),
    )
    add_metric(
        metrics,
        "netMargin",
        percent(current["profit"], current["revenue"]),
        percent(prior["profit"], prior["revenue"]),
    )
    add_metric(
        metrics,
        "roe",
        percent(current["profit"], average_equity),
        percent(prior["profit"], prior["equity"]),
    )
    add_metric(
        metrics,
        "equityRatio",
        percent(current["equity"], current["assets"]),
        percent(prior["equity"], prior["assets"]),
    )
    add_metric(
        metrics,
        "operatingCfMargin",
        percent(current["operatingCf"], current["revenue"]),
        percent(prior["operatingCf"], prior["revenue"]),
    )
    add_metric(
        metrics,
        "debtRatio",
        None
        if current["debt"] is None
        or current["equity"] is None
        or current["equity"] <= 0
        else current["debt"] / current["equity"],
    )
    add_metric(
        metrics,
        "netCash",
        None
        if current["cash"] is None or current["debt"] is None
        else (current["cash"] - current["debt"]) / 100_000_000,
    )
    add_metric(metrics, "inventoryGrowth", growth(current["inventory"], prior["inventory"]))
    add_metric(metrics, "receivablesGrowth", growth(current["receivables"], prior["receivables"]))

    history = []
    for year_end in sorted(series["revenue"])[-3:]:
        revenue = series["revenue"].get(year_end)
        equity = series["equity"].get(year_end)
        prior_equity = previous(series["equity"], year_end)
        average = (
            (equity + prior_equity) / 2
            if equity is not None and prior_equity is not None
            else equity
        )
        point = {
            "year": year_end[:7].replace("-", "/"),
            "revenue": round(revenue / 100_000_000) if revenue is not None else None,
            "operatingMargin": percent(series["operatingIncome"].get(year_end), revenue),
            "netMargin": percent(series["profit"].get(year_end), revenue),
            "roe": percent(series["profit"].get(year_end), average),
            "operatingCfMargin": percent(series["operatingCf"].get(year_end), revenue),
        }
        if all(value is not None for value in point.values()):
            history.append(
                {
                    key: round(value, 2) if isinstance(value, float) else value
                    for key, value in point.items()
                }
            )
    for key in ("operatingMargin", "netMargin", "roe", "operatingCfMargin"):
        if key in metrics and history:
            metrics[key]["trend"] = [point[key] for point in history]

    return {
        "code": str(filing["secCode"])[:4],
        "companyName": str(filing.get("filerName") or ""),
        "documentId": str(filing["docID"]),
        "filedAt": str(filing.get("submitDateTime") or ""),
        "periodEnd": period_end,
        "sourceUrl": f"https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?{filing['docID']}",
        "metrics": metrics,
        "history": history,
    }


def load_snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def load_company_codes() -> set[str]:
    payload = json.loads(COMPANY_MASTER.read_text(encoding="utf-8"))
    return {str(company["code"]) for company in payload.get("companies", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--bootstrap-days", type=int, default=460)
    parser.add_argument("--max-documents", type=int, default=4500)
    args = parser.parse_args()
    api_key = os.environ.get("EDINET_API_KEY", "").strip()
    if not api_key:
        print("EDINET_API_KEY is not configured.", file=sys.stderr)
        return 2

    snapshot = load_snapshot()
    records = snapshot.setdefault("records", {})
    current_codes = load_company_codes()
    records = {code: record for code, record in records.items() if code in current_codes}
    snapshot["records"] = records
    needs_schema_backfill = int(snapshot.get("schemaVersion") or 0) < SNAPSHOT_SCHEMA_VERSION
    days = args.bootstrap_days if not records or needs_schema_backfill else args.lookback_days
    filings, scanned = list_filings(api_key, days)
    pending = [
        filing
        for code, filing in filings.items()
        if needs_schema_backfill
        or records.get(code, {}).get("documentId") != filing.get("docID")
    ][: args.max_documents]
    updated, failures = 0, []
    for index, filing in enumerate(pending, 1):
        try:
            archive = get(f"{API}/documents/{filing['docID']}?type=1", api_key)
            record = build_record(filing, xbrl_from_zip(archive))
            if record["metrics"]:
                records[record["code"]] = record
                updated += 1
        except Exception as error:
            failures.append(f"{filing.get('secCode')}:{filing.get('docID')}: {error}")
        if index % 50 == 0:
            print(f"Processed {index}/{len(pending)}")
        time.sleep(0.08)

    snapshot.update(
        {
            "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "EDINET",
            "status": "ready",
            "message": "EDINET有価証券報告書から自動更新中。PER・PBRはJ-Quants連携時に計算します。",
            "records": records,
            "stats": {
                "companies": len(records),
                "documentsScanned": scanned,
                "documentsUpdated": updated,
            },
        }
    )
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(records)} companies; updated {updated}; skipped {len(failures)}.")
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
