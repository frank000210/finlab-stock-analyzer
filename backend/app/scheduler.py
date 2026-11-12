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
from datetime import date, datetime, time, timedelta, timezone

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


async def _brief_loop(run_hour: int, run_minute: int) -> None:
    """C9 收盤後自動掃描＋推播：每個平日產生盤後日報並發 Telegram。"""
    while True:
        delay = _seconds_until_next(run_hour, run_minute)
        logger.info("daily-brief: next run in %.1f h", delay / 3600)
        try:
            await asyncio.sleep(delay)
            from .api.risk import send_daily_brief

            result = await send_daily_brief()
            logger.info("daily-brief: sent=%s error=%s count=%s", result.get("sent"), result.get("error", ""), result.get("count"))
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("daily-brief loop error: %s", exc)
            await asyncio.sleep(300)


_brief_task: asyncio.Task | None = None


async def _store_loop(run_hour: int, run_minute: int) -> None:
    """每日資料庫：平日定時把白名單股票的資料增量寫進 MongoDB（見 data/stock_store.py）。"""
    while True:
        delay = _seconds_until_next(run_hour, run_minute)
        logger.info("stock-store: next run in %.1f h", delay / 3600)
        try:
            await asyncio.sleep(delay)
            from .data.stock_store import run_sync

            result = await run_sync(trigger="schedule")
            logger.info(
                "stock-store: symbols=%s rows=%s errors=%s aborted=%s skipped=%s",
                result.get("symbols"), result.get("rows"), result.get("errors"), result.get("aborted"), result.get("skipped"),
            )
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock-store loop error: %s", exc)
            await asyncio.sleep(300)


_store_task: asyncio.Task | None = None


def _seconds_until_next_daily(run_hour: int, run_minute: int) -> float:
    """下一個 run_hour:run_minute（台灣時間）距離現在幾秒；每天都跑，含週末。"""
    now = datetime.now(_TW)
    target = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _open_data_loop(run_hour: int, run_minute: int) -> None:
    """官方開放資料倉庫（見 data/open_data.py）：app 啟動後若資料過期就補跑一次，之後每天定時抓。
    集保是週資料、常在週末更新，所以這個排程含週末。被來源擋過會自動冷卻，不會一直重試。"""
    from .data import open_data

    try:
        await asyncio.sleep(120)  # 讓 app 先完整起來
        if await open_data.needs_catch_up():
            result = await open_data.run_sync(trigger="startup")
            logger.info("open-data: startup catch-up rows=%s errors=%s aborted=%s skipped=%s",
                        result.get("rows"), result.get("errors"), result.get("aborted"), result.get("skipped"))
    except asyncio.CancelledError:
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("open-data startup catch-up error: %s", exc)

    while True:
        delay = _seconds_until_next_daily(run_hour, run_minute)
        logger.info("open-data: next run in %.1f h", delay / 3600)
        try:
            await asyncio.sleep(delay)
            result = await open_data.run_sync(trigger="schedule")
            logger.info("open-data: rows=%s errors=%s aborted=%s skipped=%s",
                        result.get("rows"), result.get("errors"), result.get("aborted"), result.get("skipped"))
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("open-data loop error: %s", exc)
            await asyncio.sleep(300)


_open_data_task: asyncio.Task | None = None

_TW_MARKET_OPEN = time(9, 0)
_TW_MARKET_CLOSE = time(13, 35)


async def _alert_loop(interval_minutes: int) -> None:
    """C10 價格警報：只在台股盤中（週一~五 09:00-13:35）才實際檢查，避免
    收盤後浪費資料源額度做無意義的輪詢。"""
    while True:
        try:
            await asyncio.sleep(interval_minutes * 60)
            now = datetime.now(_TW)
            if now.weekday() < 5 and _TW_MARKET_OPEN <= now.time() <= _TW_MARKET_CLOSE:
                from .api.risk import run_alert_check

                result = await run_alert_check()
                if result.get("checked"):
                    logger.info(
                        "price-alert: checked=%s triggered=%s",
                        result.get("checked"), result.get("triggered"),
                    )
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("price-alert loop error: %s", exc)
            await asyncio.sleep(300)


_alert_task: asyncio.Task | None = None


def start_scheduler() -> None:
    """在 FastAPI lifespan 啟動時呼叫。"""
    global _task, _brief_task, _alert_task, _store_task, _open_data_task
    if os.getenv("AUTO_INGEST_ENABLED", "true").lower() in ("0", "false", "no", "off"):
        logger.info("auto-ingest scheduler disabled by AUTO_INGEST_ENABLED")
    elif _task is None:
        try:
            hour = int(os.getenv("AUTO_INGEST_HOUR", "15"))
            minute = int(os.getenv("AUTO_INGEST_MINUTE", "0"))
        except ValueError:
            hour, minute = 15, 0
        _task = asyncio.create_task(_loop(hour, minute))
        logger.info("auto-ingest scheduler started (daily %02d:%02d TW, weekdays)", hour, minute)

    # C9：收盤後日報推播（預設 15:35 台灣時間，平日；AUTO_BRIEF_ENABLED=false 關閉）
    if os.getenv("AUTO_BRIEF_ENABLED", "true").lower() in ("0", "false", "no", "off"):
        logger.info("daily-brief scheduler disabled by AUTO_BRIEF_ENABLED")
    elif _brief_task is None:
        try:
            b_hour = int(os.getenv("AUTO_BRIEF_HOUR", "15"))
            b_minute = int(os.getenv("AUTO_BRIEF_MINUTE", "35"))
        except ValueError:
            b_hour, b_minute = 15, 35
        _brief_task = asyncio.create_task(_brief_loop(b_hour, b_minute))
        logger.info("daily-brief scheduler started (daily %02d:%02d TW, weekdays)", b_hour, b_minute)

    # 每日資料庫：增量存白名單股票（預設 15:00 台灣時間，平日；STOCK_STORE_ENABLED=false 關閉）
    if os.getenv("STOCK_STORE_ENABLED", "true").lower() in ("0", "false", "no", "off"):
        logger.info("stock-store scheduler disabled by STOCK_STORE_ENABLED")
    elif _store_task is None:
        try:
            s_hour = int(os.getenv("STOCK_STORE_HOUR", "15"))
            s_minute = int(os.getenv("STOCK_STORE_MINUTE", "0"))
        except ValueError:
            s_hour, s_minute = 15, 0
        _store_task = asyncio.create_task(_store_loop(s_hour, s_minute))
        logger.info("stock-store scheduler started (daily %02d:%02d TW, weekdays)", s_hour, s_minute)

    # 官方開放資料倉庫：每天 21:30 台灣時間（含週末；OPEN_DATA_ENABLED=false 關閉）
    if os.getenv("OPEN_DATA_ENABLED", "true").lower() in ("0", "false", "no", "off"):
        logger.info("open-data scheduler disabled by OPEN_DATA_ENABLED")
    elif _open_data_task is None:
        try:
            o_hour = int(os.getenv("OPEN_DATA_HOUR", "21"))
            o_minute = int(os.getenv("OPEN_DATA_MINUTE", "30"))
        except ValueError:
            o_hour, o_minute = 21, 30
        _open_data_task = asyncio.create_task(_open_data_loop(o_hour, o_minute))
        logger.info("open-data scheduler started (daily %02d:%02d TW, incl. weekends)", o_hour, o_minute)

    # C10：價格警報，盤中每 N 分鐘檢查一次（預設 20 分鐘；PRICE_ALERT_ENABLED=false 關閉）
    if os.getenv("PRICE_ALERT_ENABLED", "true").lower() in ("0", "false", "no", "off"):
        logger.info("price-alert scheduler disabled by PRICE_ALERT_ENABLED")
    elif _alert_task is None:
        try:
            interval = int(os.getenv("PRICE_ALERT_INTERVAL_MIN", "20"))
        except ValueError:
            interval = 20
        _alert_task = asyncio.create_task(_alert_loop(interval))
        logger.info("price-alert scheduler started (every %d min, market hours TW weekdays)", interval)


def stop_scheduler() -> None:
    global _task, _brief_task, _alert_task, _store_task, _open_data_task
    if _open_data_task is not None:
        _open_data_task.cancel()
        _open_data_task = None
    if _store_task is not None:
        _store_task.cancel()
        _store_task = None
    if _task is not None:
        _task.cancel()
        _task = None
    if _brief_task is not None:
        _brief_task.cancel()
        _brief_task = None
    if _alert_task is not None:
        _alert_task.cancel()
        _alert_task = None
