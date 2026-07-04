"""TWSE sector (industry) index daily close crawler."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

BENCHMARK_NAME = "發行量加權股價指數"
BENCHMARK_ID = "TAIEX"

# 排除聚合型類指數，保留單一產業類指數
_EXCLUDED_SECTORS = {
    "水泥窯製類指數",
    "塑膠化工類指數",
    "機電類指數",
    "化學生技醫療類指數",
    "電子工業類指數",
}


def _parse_number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text in {"--", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _sector_id(name: str) -> str:
    return name.replace("類指數", "").strip()


class SectorIndexCrawler:
    """Fetch TWSE daily price-index closes (sector indices + TAIEX benchmark)."""

    def __init__(self, request_delay: float = 0.3, timeout: float = 20.0) -> None:
        self.request_delay = request_delay
        self.timeout = timeout

    async def get_day(self, target_date: date) -> list[dict[str, Any]]:
        """Return [{sector_id, name, close, is_benchmark}] for one trading day.

        Empty list when the market was closed (TWSE stat != OK).
        """
        params = {
            "date": target_date.strftime("%Y%m%d"),
            "type": "IND",
            "response": "json",
        }
        async with httpx.AsyncClient(timeout=self.timeout, headers=_HEADERS) as client:
            response = await client.get(_MI_INDEX_URL, params=params)
            response.raise_for_status()
            payload = response.json()

        if str(payload.get("stat", "")).upper() != "OK":
            return []

        rows: list[dict[str, Any]] = []
        for table in payload.get("tables", []):
            fields = table.get("fields") or []
            if not fields or "收盤指數" not in fields:
                continue
            title = str(table.get("title", ""))
            if "價格指數" not in title or "臺灣證券交易所" not in title:
                continue
            for record in table.get("data", []):
                if len(record) < 2:
                    continue
                name = str(record[0] or "").strip()
                close = _parse_number(record[1])
                if close is None:
                    continue
                if name == BENCHMARK_NAME:
                    rows.append(
                        {
                            "sector_id": BENCHMARK_ID,
                            "name": name,
                            "close": close,
                            "is_benchmark": True,
                        }
                    )
                elif name.endswith("類指數") and name not in _EXCLUDED_SECTORS:
                    rows.append(
                        {
                            "sector_id": _sector_id(name),
                            "name": name,
                            "close": close,
                            "is_benchmark": False,
                        }
                    )
            break
        return rows

    async def get_days(
        self,
        target_dates: list[date],
        concurrency: int = 3,
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch multiple days politely; returns {iso_date: rows}."""
        semaphore = asyncio.Semaphore(concurrency)
        results: dict[str, list[dict[str, Any]]] = {}

        async def fetch(day: date) -> None:
            async with semaphore:
                try:
                    rows = await self.get_day(day)
                except Exception as e:
                    logger.warning("Sector index fetch failed for %s: %s", day.isoformat(), e)
                    rows = []
                results[day.isoformat()] = rows
                await asyncio.sleep(self.request_delay)

        await asyncio.gather(*(fetch(day) for day in target_dates))
        return results
