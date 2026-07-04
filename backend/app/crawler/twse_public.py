"""TWSE/MOPS public data crawler."""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from datetime import date, timedelta
from html import unescape
from html.parser import HTMLParser
from typing import Any

import httpx
import pandas as pd

from .finmind_client import FinMindClient

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL = 1800  # 30 minutes


def _clear_cache() -> int:
    count = len(_cache)
    _cache.clear()
    return count


try:
    from ..db.memory_cache import register as _register_memory_cache

    _register_memory_cache("twse_public", lambda: len(_cache), _clear_cache)
except Exception:  # registry 不可用時不影響本模組運作
    pass

_MOPS_URL = "https://mops.twse.com.tw/mops/web/ajax_t05st01"
_MATERIAL_INFO_URL = "https://www.twse.com.tw/rwd/zh/announcement/materialInfo"
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}
_BOARD_KEYWORDS = ("董事會", "董事會決議", "board")
_FINANCIAL_KEYWORDS = ("財報", "財務", "營收", "每股盈餘", "EPS")


def _make_cache_key(symbol: str) -> str:
    return hashlib.md5(symbol.strip().upper().encode()).hexdigest()


def _get_cached(key: str) -> dict[str, Any] | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return data


def _set_cached(key: str, data: dict[str, Any]) -> None:
    _cache[key] = (time.time(), data)
    if len(_cache) > 200:
        oldest_key = min(_cache, key=lambda item: _cache[item][0])
        del _cache[oldest_key]


def _clean_text(value: Any) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    return text


def _pick_value(record: dict[str, Any], keywords: tuple[str, ...]) -> str:
    for key, value in record.items():
        key_text = _clean_text(key)
        if any(keyword in key_text for keyword in keywords):
            cleaned = _clean_text(value)
            if cleaned:
                return cleaned
    return ""


def _looks_like_data_row(values: list[str]) -> bool:
    return any(value for value in values) and len(values) > 1


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._cell_parts: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []
        elif tag == "br" and self._in_cell:
            self._cell_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._in_cell:
            self._in_cell = False
            self._current_row.append(_clean_text("".join(self._cell_parts)))
        elif tag == "tr" and _looks_like_data_row(self._current_row):
            self.rows.append(self._current_row[:])


def _rows_to_records(rows: list[list[str]]) -> list[dict[str, str]]:
    if len(rows) < 2:
        return []

    headers = [_clean_text(cell) or f"col_{idx}" for idx, cell in enumerate(rows[0])]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        if not any(row):
            continue
        padded = row + [""] * max(0, len(headers) - len(row))
        record = {
            headers[idx]: _clean_text(padded[idx]) for idx in range(min(len(headers), len(padded)))
        }
        if any(record.values()):
            records.append(record)
    return records


def _record_to_public_item(record: dict[str, Any], source: str) -> dict[str, str]:
    date_value = _pick_value(record, ("日期", "日", "Date"))
    title_value = _pick_value(record, ("主旨", "標題", "摘要", "事由", "Title"))
    content_value = _pick_value(record, ("內容", "說明", "符合條款", "重大訊息", "Description"))

    fallback_values = [
        _clean_text(value) for value in record.values() if _clean_text(value)
    ]
    if not title_value and fallback_values:
        title_value = fallback_values[min(2, len(fallback_values) - 1)]
    if not content_value:
        content_value = title_value

    return {
        "date": date_value,
        "title": title_value,
        "content": content_value,
        "source": source,
    }


def _dedupe_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str]] = set()
    results: list[dict[str, str]] = []
    for item in items:
        normalized = {
            "date": _clean_text(item.get("date", "")),
            "title": _clean_text(item.get("title", "")),
            "content": _clean_text(item.get("content", "")),
            "source": _clean_text(item.get("source", "")),
        }
        if not normalized["title"] and not normalized["content"]:
            continue
        key = (
            normalized["date"],
            normalized["title"],
            normalized["content"],
            normalized["source"],
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    return results


def _material_records_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    fields = payload.get("fields")
    data_rows = payload.get("data")
    if isinstance(fields, list) and isinstance(data_rows, list):
        for row in data_rows:
            if isinstance(row, dict):
                records.append(row)
            elif isinstance(row, list):
                records.append(
                    {
                        _clean_text(fields[idx]): row[idx] if idx < len(row) else ""
                        for idx in range(len(fields))
                    }
                )

    tables = payload.get("tables")
    if isinstance(tables, list):
        for table in tables:
            if not isinstance(table, dict):
                continue
            table_fields = table.get("fields") or fields or []
            table_data = table.get("data") or []
            for row in table_data:
                if isinstance(row, dict):
                    records.append(row)
                elif isinstance(row, list):
                    records.append(
                        {
                            _clean_text(table_fields[idx]): row[idx] if idx < len(row) else ""
                            for idx in range(len(table_fields))
                        }
                    )

    return records


def _extract_board_resolutions(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        item
        for item in items
        if any(keyword in f"{item['title']} {item['content']}" for keyword in _BOARD_KEYWORDS)
    ]


def _extract_financial_announcement(items: list[dict[str, str]]) -> dict[str, str] | None:
    for item in items:
        if any(keyword in f"{item['title']} {item['content']}" for keyword in _FINANCIAL_KEYWORDS):
            return item
    return None


class TwsePublicCrawler:
    """Fetch TWSE/MOPS public datasets for a stock symbol."""

    async def _fetch_mops_announcements(
        self, client: httpx.AsyncClient, symbol: str
    ) -> list[dict[str, str]]:
        response = await client.post(
            _MOPS_URL,
            data={"co_id": symbol},
            headers={
                **_DEFAULT_HEADERS,
                "Referer": "https://mops.twse.com.tw/mops/web/t05st01",
                "Origin": "https://mops.twse.com.tw",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        response.raise_for_status()
        if "FOR SECURITY REASONS" in response.text:
            raise ValueError("MOPS blocked the request")

        parser = _TableParser()
        parser.feed(response.text)
        records = _rows_to_records(parser.rows)
        return _dedupe_items([
            _record_to_public_item(record, "mops") for record in records
        ])

    async def _fetch_material_info(
        self, client: httpx.AsyncClient, symbol: str
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        response = await client.get(
            _MATERIAL_INFO_URL,
            params={"stockNo": symbol, "response": "json"},
            headers={**_DEFAULT_HEADERS, "Accept": "application/json,text/plain,*/*"},
        )
        response.raise_for_status()

        payload = response.json()
        records = _material_records_from_payload(payload)
        items = _dedupe_items([
            _record_to_public_item(record, "twse-material-info") for record in records
        ])
        return items, _extract_board_resolutions(items)

    async def _fetch_dividends(self, symbol: str) -> list[dict[str, Any]]:
        finmind = FinMindClient()
        start = "2000-01-01"
        end = date.today().isoformat()
        df = await finmind.get_dividend_history(symbol, start, end)
        if df.empty:
            return []

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        if df.empty:
            return []

        df["year_value"] = df["date"].dt.year
        df["cash_total"] = (
            pd.to_numeric(df.get("CashEarningsDistribution"), errors="coerce").fillna(0.0)
            + pd.to_numeric(df.get("CashStatutorySurplus"), errors="coerce").fillna(0.0)
        )
        df["stock_total"] = (
            pd.to_numeric(df.get("StockEarningsDistribution"), errors="coerce").fillna(0.0)
            + pd.to_numeric(df.get("StockStatutorySurplus"), errors="coerce").fillna(0.0)
        )

        grouped = (
            df.groupby("year_value", as_index=False)[["cash_total", "stock_total"]]
            .sum()
            .sort_values("year_value", ascending=False)
        )

        results: list[dict[str, Any]] = []
        for _, row in grouped.iterrows():
            cash = float(row["cash_total"])
            stock = float(row["stock_total"])
            results.append(
                {
                    "year": int(row["year_value"]),
                    "cash": round(cash, 4),
                    "stock": round(stock, 4),
                    "total": round(cash + stock, 4),
                }
            )
        return results

    async def _fetch_financial_summary(self, symbol: str) -> dict[str, Any]:
        finmind = FinMindClient()
        today = date.today()
        revenue_start = (today - timedelta(days=800)).isoformat()
        financial_start = (today - timedelta(days=1500)).isoformat()
        revenue_df, financial_df = await asyncio.gather(
            finmind.get_monthly_revenue(symbol, revenue_start, today.isoformat()),
            finmind.get_financial_statements(symbol, financial_start, today.isoformat()),
        )

        summary: dict[str, Any] = {
            "revenue_latest": None,
            "revenue_latest_month": None,
            "revenue_yoy_pct": None,
            "eps_latest": None,
            "eps_report_date": None,
        }

        if not revenue_df.empty:
            revenue_df = revenue_df.copy()
            revenue_df["date"] = pd.to_datetime(revenue_df["date"], errors="coerce")
            revenue_df = revenue_df.dropna(subset=["date"]).sort_values("date")
            if not revenue_df.empty:
                latest_revenue = revenue_df.iloc[-1]
                latest_value = pd.to_numeric(pd.Series([latest_revenue.get("revenue")]), errors="coerce").iloc[0]
                summary["revenue_latest"] = float(latest_value) if pd.notna(latest_value) else None
                summary["revenue_latest_month"] = latest_revenue["date"].strftime("%Y-%m")

                revenue_month = latest_revenue["date"].month
                prior_year = latest_revenue["date"].year - 1
                previous = revenue_df[
                    (revenue_df["date"].dt.year == prior_year)
                    & (revenue_df["date"].dt.month == revenue_month)
                ]
                if not previous.empty:
                    prev_value = pd.to_numeric(
                        pd.Series([previous.iloc[-1].get("revenue")]), errors="coerce"
                    ).iloc[0]
                    if pd.notna(prev_value) and prev_value:
                        summary["revenue_yoy_pct"] = round(
                            ((float(latest_value) - float(prev_value)) / float(prev_value)) * 100,
                            2,
                        )

        if not financial_df.empty:
            financial_df = financial_df.copy()
            financial_df["date"] = pd.to_datetime(financial_df["date"], errors="coerce")
            eps_df = financial_df[
                (financial_df["type"] == "EPS") & financial_df["date"].notna()
            ].sort_values("date")
            if not eps_df.empty:
                latest_eps = eps_df.iloc[-1]
                eps_value = pd.to_numeric(pd.Series([latest_eps.get("value")]), errors="coerce").iloc[0]
                summary["eps_latest"] = float(eps_value) if pd.notna(eps_value) else None
                summary["eps_report_date"] = latest_eps["date"].strftime("%Y-%m-%d")

        return summary

    async def get_public_data(self, symbol: str) -> dict[str, Any]:
        cache_key = _make_cache_key(symbol)
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        announcements: list[dict[str, str]] = []
        board_meeting_resolutions: list[dict[str, str]] = []
        dividends: list[dict[str, Any]] = []
        financial_summary: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            results = await asyncio.gather(
                self._fetch_mops_announcements(client, symbol),
                self._fetch_material_info(client, symbol),
                self._fetch_dividends(symbol),
                self._fetch_financial_summary(symbol),
                return_exceptions=True,
            )

        mops_result, material_result, dividends_result, financial_result = results

        try:
            if not isinstance(mops_result, Exception):
                announcements.extend(mops_result)
        except Exception:
            pass

        try:
            if not isinstance(material_result, Exception):
                material_announcements, board_meeting_resolutions = material_result
                announcements.extend(material_announcements)
        except Exception:
            board_meeting_resolutions = []

        try:
            if not isinstance(dividends_result, Exception):
                dividends = dividends_result
        except Exception:
            dividends = []

        try:
            if not isinstance(financial_result, Exception):
                financial_summary = financial_result
        except Exception:
            financial_summary = {}

        announcements = _dedupe_items(announcements)
        board_meeting_resolutions = _dedupe_items(board_meeting_resolutions)

        latest_financial_announcement = _extract_financial_announcement(announcements)
        if latest_financial_announcement:
            financial_summary = {
                **financial_summary,
                "latest_financial_announcement": latest_financial_announcement,
            }

        data = {
            "symbol": symbol,
            "announcements": announcements,
            "board_meeting_resolutions": board_meeting_resolutions,
            "dividends": dividends,
            "financial_summary": financial_summary,
        }
        _set_cached(cache_key, data)
        return data
