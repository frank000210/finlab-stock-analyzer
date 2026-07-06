"""每日收盤後自動 re-ingest 關聯圖/類股輪動資料的排程。

不引入額外套件：用一個 asyncio 背景任務，算出下一次執行時間、睡到那時、
執行 ingest，然後重排。台股 13:30 收盤，預設 15:00（台灣時間）跑，週末略過。

可用環境變數調整：
- AUTO_INGEST_ENABLED  預設 true；設 false/0/no 關閉
- AUTO_INGEST_HOUR     預設 15（台灣時間，24 小時制）
- AUTO_INGEST_MINUTE   預設 0
- AUTO_INGEST_SYMBOLS  逗號分隔；有值才會 re-ingest 關聯圖觀察池原始資料
                       （類股輪動 twse 指數為全市場、不需 symbols，一定會跑）
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_TW = timezone(timedelta(hours=8))
_task: asyncio.Task | None = None


async def _run_once() -> None:
    """跑一次完整的 re-ingest：類股輪動指數 +（可選）關聯圖觀察池，最後清快取。"""
    from .analysis.sector_rotation import ingest_sector_index
    from .analysis.watch_graph import ingest_watchlist_raw
    from .db.memcache import mem_clear

    end = date.today()

    # 類股輪動：官方類股指數，全市場、不需 symbols
    try:
        result = await ingest_sector_index(end - timedelta(days=420), end)
        logger.info("scheduled ingest: sector index ok (%s)", result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduled ingest: sector index failed: %s", exc)

    # 關聯圖：需要觀察池，改由環境變數指定要自動更新哪些代碼
    symbols_env = os.getenv("AUTO_INGEST_SYMBOLS", "").strip()
    symbols = [s.strip().upper() for s in symbols_env.split(",") if s.strip()]
    if symbols:
        try:
            result = await ingest_watchlist_raw(symbols, end - timedelta(days=90), end)
            logger.info("scheduled ingest: watchlist %d symbols ok (%s)", len(symbols), result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduled ingest: watchlist failed: %s", exc)

    # 清掉圖/輪動的記憶體快取，讓下次請求用最新資料重算
    mem_clear("rotation:")
    mem_clear("graph:")


def _seconds_until_next(run_hour: int, run_minute: int) -> float:
    now = datetime.now(_TW)
    target = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    while target.weekday() >= 5:  # 5=Sat, 6=Sun → 推到週一
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _loop(run_hour: int, run_minute: int) -> None:
    while True:
        delay = _seconds_until_next(run_hour, run_minute)
        logger.info("auto-ingest: next run in %.1f h", delay / 3600)
        try:
            await asyncio.sleep(delay)
            await _run_once()
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-ingest loop error: %s", exc)
            await asyncio.sleep(300)  # 出錯後短暫退避再繼續


def start_scheduler() -> None:
    """在 FastAPI lifespan 啟動時呼叫。"""
    if os.getenv("AUTO_INGEST_ENABLED", "true").lower() in ("0", "false", "no", "off"):
        logger.info("auto-ingest scheduler disabled by AUTO_INGEST_ENABLED")
        return
    global _task
    if _task is not None:
        return
    try:
        hour = int(os.getenv("AUTO_INGEST_HOUR", "15"))
        minute = int(os.getenv("AUTO_INGEST_MINUTE", "0"))
    except ValueError:
        hour, minute = 15, 0
    _task = asyncio.create_task(_loop(hour, minute))
    logger.info("auto-ingest scheduler started (daily %02d:%02d TW, weekdays)", hour, minute)


def stop_scheduler() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
