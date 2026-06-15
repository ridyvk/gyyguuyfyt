#!/usr/bin/env python3
"""Supplement KPI Scope financials with free TDnet earnings XBRL."""

from __future__ import annotations

import argparse
import html.parser
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from update_edinet_financials import (
    DEBT_COMPONENTS,
    FACT_NAMES,
    add_metric,
    at,
    growth,
    percent,
    previous,
)

BASE_URL = "https://www.release.tdnet.info/inbs"
SNAPSHOT = Path(__file__).resolve().parents[1] / "public/data/financials.json"
COMPANY_MASTER = (
    Path(__file__).resolve().parents[1] / "src/data/listedCompanies.json"
)
JST = timezone(timedelta(hours=9))

TDNET_FACT_NAMES = {
    **FACT_NAMES,
    "operatingIncome": FACT_NAMES["operatingIncome"]
    + ("OperatingIncomeIFRS",),
    "operatingCf": FACT_NAMES["operatingCf"]
    + (
        "CashFlowsFromOperatingActivitiesIFRS",
        "NetCashProvidedByUsedInOperatingActivitiesIFRS",
    ),
    "receivables": FACT_NAMES["receivables"]
    + (
        "TradeAndOtherReceivablesCAIFRS",
        "TradeAndOtherReceivablesCurrentIFRS",
    ),
}
TDNET_DEBT_COMPONENTS = DEBT_COMPONENTS + (
    "BorrowingsCLIFRS",
    "BorrowingsNCLIFRS",
    "LeaseLiabilitiesCLIFRS",
    "LeaseLiabilitiesNCLIFRS",
)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def get(url: str, retries: int = 4) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "KPI-Scope/1.0 (+financial research app)"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except urllib.error.HTTPError:
            raise
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("request failed")


class TDnetListParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self.row: dict[str, str] | None = None
        self.field: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self.row = {}
            return
        if self.row is None:
            return
        if tag == "td":
            classes = set((attributes.get("class") or "").split())
            for field, class_name in (
                ("time", "kjTime"),
                ("code", "kjCode"),
                ("companyName", "kjName"),
                ("title", "kjTitle"),
                ("xbrl", "kjXbrl"),
            ):
                if class_name in classes:
                    self.field = field
                    self.row.setdefault(field, "")
                    break
        elif tag == "a" and self.field in {"title", "xbrl"}:
            href = attributes.get("href")
            if href:
                self.row[f"{self.field}Href"] = href

    def handle_data(self, data: str) -> None:
        if self.row is not None and self.field:
            self.row[self.field] = self.row.get(self.field, "") + data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self.field = None
        elif tag == "tr" and self.row is not None:
            row = {
                key: re.sub(r"\s+", " ", value).strip()
                for key, value in self.row.items()
            }
            if row.get("code") and row.get("title") and row.get("xbrlHref"):
                self.rows.append(row)
            self.row = None
            self.field = None


def parse_list_page(payload: bytes) -> tuple[list[dict[str, str]], int]:
    text = payload.decode("utf-8", errors="replace")
    parser = TDnetListParser()
    parser.feed(text)
    pages = [
        int(match)
        for match in re.findall(r"I_list_(\d{3})_\d{8}\.html", text)
    ]
    return parser.rows, max(pages, default=1)


def filing_timestamp(target: date, filing_time: str) -> str:
    try:
        hour, minute = [int(part) for part in filing_time.split(":", 1)]
    except (TypeError, ValueError):
        hour, minute = 0, 0
    return datetime(
        target.year,
        target.month,
        target.day,
        hour,
        minute,
        tzinfo=JST,
    ).isoformat()


def list_filings(days: int) -> tuple[dict[str, dict], int]:
    latest: dict[str, dict] = {}
    scanned = 0
    today = datetime.now(JST).date()
    for offset in range(days):
        target = today - timedelta(days=offset)
        date_token = target.strftime("%Y%m%d")
        try:
            first_payload = get(
                f"{BASE_URL}/I_list_001_{date_token}.html"
            )
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue
            raise
        rows, pages = parse_list_page(first_payload)
        all_rows = list(rows)
        for page in range(2, pages + 1):
            payload = get(
                f"{BASE_URL}/I_list_{page:03d}_{date_token}.html"
            )
            page_rows, _ = parse_list_page(payload)
            all_rows.extend(page_rows)
        scanned += len(all_rows)
        for row in all_rows:
            if "決算短信" not in row.get("title", ""):
                continue
            code = row.get("code", "")[:4]
            if len(code) != 4:
                continue
            filed_at = filing_timestamp(target, row.get("time", ""))
            filing = {
                "code": code,
                "companyName": row.get("companyName", ""),
                "title": row.get("title", ""),
                "filedAt": filed_at,
                "pdfUrl": f"{BASE_URL}/{row.get('titleHref', '')}",
                "xbrlUrl": f"{BASE_URL}/{row['xbrlHref']}",
                "documentId": Path(row["xbrlHref"]).stem,
            }
            current = latest.get(code)
            if current is None or (
                filed_at,
                filing["documentId"],
            ) > (
                current["filedAt"],
                current["documentId"],
            ):
                latest[code] = filing
        time.sleep(0.04)
    return latest, scanned


def inline_number(element: ET.Element) -> float | None:
    text = "".join(element.itertext()).strip()
    text = text.replace(",", "").replace("△", "-").replace("▲", "-")
    text = re.sub(r"[^0-9.()\-]", "", text)
    if not text:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    try:
        value = float(text)
        value *= 10 ** int(element.attrib.get("scale") or 0)
        if element.attrib.get("sign") == "-":
            value = -abs(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def parse_inline_xbrl(
    archive_data: bytes,
) -> tuple[dict[str, dict], dict[str, list[tuple[str, float]]]]:
    contexts: dict[str, dict] = {}
    facts: dict[str, list[tuple[str, float]]] = defaultdict(list)
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith(("-ixbrl.htm", "-ixbrl.html"))
        ]
        if not names:
            names = [
                name
                for name in archive.namelist()
                if name.lower().endswith((".htm", ".html"))
                and "xbrldata" in name.lower()
            ]
        if not names:
            raise ValueError("TDnet Inline XBRL document not found")
        for name in names:
            root = ET.fromstring(archive.read(name))
            for element in root.iter():
                if (
                    local_name(element.tag) != "context"
                    or not element.attrib.get("id")
                ):
                    continue
                context = {
                    "start": None,
                    "end": None,
                    "instant": None,
                    "dimensions": [],
                }
                for child in element.iter():
                    child_name = local_name(child.tag)
                    text = (child.text or "").strip()
                    if child_name in {"startDate", "endDate", "instant"}:
                        context[
                            {
                                "startDate": "start",
                                "endDate": "end",
                                "instant": "instant",
                            }[child_name]
                        ] = text
                    elif child_name in {"explicitMember", "typedMember"}:
                        context["dimensions"].append(text or "typedMember")
                contexts[element.attrib["id"]] = context
            for element in root.iter():
                if local_name(element.tag) != "nonFraction":
                    continue
                context_id = element.attrib.get("contextRef")
                fact_name = local_name(element.attrib.get("name", ""))
                value = inline_number(element)
                if context_id in contexts and fact_name and value is not None:
                    facts[fact_name].append((context_id, value))
    return contexts, facts


def is_actual_consolidated(context_id: str, context: dict) -> bool:
    text = context_id + " " + " ".join(context["dimensions"])
    rejected = (
        "NonConsolidated",
        "ForecastMember",
        "UpperMember",
        "LowerMember",
        "NextYear",
    )
    return not any(token in text for token in rejected)


def context_rank(context_id: str, context: dict, period_end: str) -> int:
    text = context_id + " " + " ".join(context["dimensions"])
    return (
        (40 if (context["instant"] or context["end"]) == period_end else 0)
        + (30 if not context["dimensions"] else 0)
        + (20 if "ConsolidatedMember" in text else 0)
        + (8 if "ResultMember" in text else 0)
        + (6 if "CurrentYear" in context_id else 0)
    )


def values_for(
    contexts: dict,
    facts: dict,
    names: tuple[str, ...],
    duration: bool,
) -> dict[str, float]:
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for name in names:
        for context_id, value in facts.get(name, []):
            context = contexts[context_id]
            period_end = context["end"] if duration else context["instant"]
            if (
                not period_end
                or not is_actual_consolidated(context_id, context)
            ):
                continue
            if duration:
                try:
                    days = (
                        date.fromisoformat(context["end"])
                        - date.fromisoformat(context["start"])
                    ).days
                except (TypeError, ValueError):
                    continue
                if not 45 <= days <= 460:
                    continue
            grouped[period_end].append((context_id, value))
    return {
        period_end: max(
            candidates,
            key=lambda candidate: context_rank(
                candidate[0],
                contexts[candidate[0]],
                period_end,
            ),
        )[1]
        for period_end, candidates in grouped.items()
    }


def infer_period_end(contexts: dict) -> str:
    candidates: list[str] = []
    for context_id, context in contexts.items():
        if not is_actual_consolidated(context_id, context):
            continue
        if "CurrentYear" not in context_id:
            continue
        period_end = context["end"] or context["instant"]
        if period_end:
            candidates.append(period_end)
    if not candidates:
        raise ValueError("Current TDnet reporting period was not found")
    return max(candidates)


def build_record(filing: dict, archive_data: bytes) -> dict:
    contexts, facts = parse_inline_xbrl(archive_data)
    period_end = infer_period_end(contexts)
    series = {
        key: values_for(
            contexts,
            facts,
            names,
            key in {"revenue", "operatingIncome", "profit", "operatingCf"},
        )
        for key, names in TDNET_FACT_NAMES.items()
    }
    if not series["debt"]:
        debt: dict[str, float] = defaultdict(float)
        for name in TDNET_DEBT_COMPONENTS:
            for key, value in values_for(
                contexts,
                facts,
                (name,),
                False,
            ).items():
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
    add_metric(
        metrics,
        "revenueGrowth",
        growth(current["revenue"], prior["revenue"]),
    )
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
    add_metric(
        metrics,
        "inventoryGrowth",
        growth(current["inventory"], prior["inventory"]),
    )
    add_metric(
        metrics,
        "receivablesGrowth",
        growth(current["receivables"], prior["receivables"]),
    )

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
            "revenue": (
                round(revenue / 100_000_000)
                if revenue is not None
                else None
            ),
            "operatingMargin": percent(
                series["operatingIncome"].get(year_end),
                revenue,
            ),
            "netMargin": percent(series["profit"].get(year_end), revenue),
            "roe": percent(series["profit"].get(year_end), average),
            "operatingCfMargin": percent(
                series["operatingCf"].get(year_end),
                revenue,
            ),
        }
        if all(value is not None for value in point.values()):
            history.append(
                {
                    key: (
                        round(value, 2)
                        if isinstance(value, float)
                        else value
                    )
                    for key, value in point.items()
                }
            )
    for key in (
        "operatingMargin",
        "netMargin",
        "roe",
        "operatingCfMargin",
    ):
        if key in metrics and history:
            metrics[key]["trend"] = [point[key] for point in history]

    return {
        "code": filing["code"],
        "companyName": filing["companyName"],
        "documentId": filing["documentId"],
        "filedAt": filing["filedAt"],
        "periodEnd": period_end,
        "source": "TDnet",
        "sourceUrl": filing["pdfUrl"],
        "metrics": metrics,
        "history": history,
    }


def merge_history(existing: dict | None, record: dict) -> None:
    points = {
        point["year"]: point
        for point in (existing or {}).get("history", [])
        if point.get("year")
    }
    for point in record.get("history", []):
        points[point["year"]] = point
    record["history"] = [points[key] for key in sorted(points)[-3:]]
    for key in (
        "operatingMargin",
        "netMargin",
        "roe",
        "operatingCfMargin",
    ):
        if key in record["metrics"] and record["history"]:
            record["metrics"][key]["trend"] = [
                point[key]
                for point in record["history"]
                if key in point
            ]


def should_replace(existing: dict | None, record: dict) -> bool:
    if existing is None:
        return True
    old_key = (
        str(existing.get("periodEnd") or ""),
        str(existing.get("filedAt") or ""),
    )
    return (record["periodEnd"], record["filedAt"]) > old_key


def load_company_codes() -> set[str]:
    payload = json.loads(COMPANY_MASTER.read_text(encoding="utf-8"))
    return {
        str(company["code"])
        for company in payload.get("companies", [])
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=31)
    parser.add_argument("--max-documents", type=int, default=1500)
    parser.add_argument("--only-code")
    parser.add_argument("--archive-url")
    parser.add_argument("--pdf-url")
    parser.add_argument("--filed-at")
    parser.add_argument("--company-name")
    args = parser.parse_args()

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    records = snapshot.setdefault("records", {})
    current_codes = load_company_codes()
    records = {
        code: record
        for code, record in records.items()
        if code in current_codes
    }
    snapshot["records"] = records

    if args.only_code and args.archive_url:
        filings = {
            args.only_code: {
                "code": args.only_code,
                "companyName": args.company_name or args.only_code,
                "title": "決算短信",
                "filedAt": args.filed_at or datetime.now(JST).isoformat(),
                "pdfUrl": args.pdf_url or args.archive_url,
                "xbrlUrl": args.archive_url,
                "documentId": Path(args.archive_url).stem,
            }
        }
        scanned = 1
    else:
        filings, scanned = list_filings(args.lookback_days)

    updated = 0
    failures: list[str] = []
    candidates = list(filings.values())[: args.max_documents]
    for index, filing in enumerate(candidates, 1):
        try:
            existing = records.get(filing["code"])
            if (existing or {}).get("documentId") == filing["documentId"]:
                continue
            record = build_record(filing, get(filing["xbrlUrl"]))
            if record["metrics"] and should_replace(existing, record):
                merge_history(existing, record)
                records[record["code"]] = record
                updated += 1
        except Exception as error:
            failures.append(
                f"{filing.get('code')}:{filing.get('documentId')}: {error}"
            )
        if index % 50 == 0:
            print(f"Processed {index}/{len(candidates)}")
        time.sleep(0.06)

    has_tdnet = any(
        record.get("source") == "TDnet"
        for record in records.values()
    )
    snapshot.update(
        {
            "generatedAt": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "source": "EDINET+TDnet" if has_tdnet else "EDINET",
            "status": "ready",
            "message": (
                "EDINET有価証券報告書とTDnet決算短信を自動統合中。"
                "企業ごとに新しい開示を優先します。"
            ),
            "records": records,
            "stats": {
                **snapshot.get("stats", {}),
                "companies": len(records),
                "tdnetDocumentsScanned": scanned,
                "tdnetDocumentsUpdated": updated,
            },
        }
    )
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(records)} companies; "
        f"TDnet updated {updated}; skipped {len(failures)}."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
