"""本地資料庫優先讀取層（md_* 每日資料庫 ＋ od_* 官方開放資料倉庫）。

職責
- 讓個股分析、評分卡、籌碼、估值、月營收等路徑**優先讀取本地 MongoDB**
  （`md_price` / `md_institutional` / `md_margin` / `md_valuation` / `md_revenue`
  與全市場 `od_margin` / `od_valuation` / `od_revenue`），命中時完全不消耗
  FinMind 免費版額度（600 次/時）。
- 嚴格保證回傳格式（DataFrame 欄位名稱、日期型別、數值單位、欄位順序）與
  `FinMindClient` 對應方法 **100% 相容**。
- 查無資料、區間涵蓋不足（過早或不夠新）、或 MongoDB 異常／逾時，一律回傳
  `None`（不拋例外），讓呼叫端無縫回落原本的 FinMind API 路徑。

資料集對照與優先順序
- price         : md_price
- institutional : md_institutional
- margin        : md_margin → od_margin（兩者可依日期互補合併）
- valuation     : md_valuation → od_valuation（兩者可依日期互補合併）
- revenue       : md_revenue → od_revenue（兩者可依日期互補合併；od_revenue 千元轉元）
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

from . import open_data as od
from . import stock_store as st
from .us_symbols import is_tw_symbol, normalize_symbol

logger = logging.getLogger(__name__)

# 查詢單檔股票走索引通常僅需數毫秒；逾時即視為資料庫異常，快速回落 FinMind
DB_READ_TIMEOUT_SEC = 1.5
# 真實 MongoDB 失敗／逾時後的短暫冷卻秒數，避免同一頁面多併發查詢重複等待逾時
DB_ERROR_COOLDOWN_SEC = 30.0

# 涵蓋度判定寬容度
DAILY_START_SLACK_LONG = 14      # 長區間（>=30 天）或庫內已有更早紀錄：容許春節最長連假
DAILY_START_SLACK_SHORT = 5      # 短區間（<30 天）且無更早紀錄：容許週末與一般連假，防止僅 1 天誤判命中
DAILY_END_SLACK_BDAYS = 1        # 容許落後至多 1 個平日（盤中尚未收盤、盤後延遲、單日國定假日、融資晚一天）
MONTHLY_START_SLACK_DAYS = 45    # 月營收起點寬容（約一個半月）

_db_cooldown_until: float = 0.0

# FinMind 融資融券標準欄位順序：YesterdayBalance 放 TodayBalance 之前，
# 確保下游（如 major_players.py 迴圈比對欄位名）永遠取到今日餘額。
_MARGIN_COLUMNS = [
    "date",
    "stock_id",
    "MarginPurchaseBuy",
    "MarginPurchaseCashRepayment",
    "MarginPurchaseLimit",
    "MarginPurchaseSell",
    "MarginPurchaseYesterdayBalance",
    "MarginPurchaseTodayBalance",
    "OffsetLoanAndShort",
    "ShortSaleBuy",
    "ShortSaleCashRepayment",
    "ShortSaleLimit",
    "ShortSaleSell",
    "ShortSaleYesterdayBalance",
    "ShortSaleTodayBalance",
    "Note",
]


def reset_cooldown() -> None:
    """清除真實 DB 失敗冷卻（主要供測試隔離使用）。"""
    global _db_cooldown_until
    _db_cooldown_until = 0.0


# ───────────────────────── 純函式：日期與覆蓋判定 ─────────────────────────

def _normalize_query_symbol(symbol: str) -> Optional[str]:
    """僅對台股代號與加權指數 TAIEX 查本地庫；美股與國際指數直接回 None 跳過。"""
    sym = normalize_symbol(symbol)
    if not sym:
        return None
    if is_tw_symbol(sym) or sym == "TAIEX":
        return sym
    return None


def parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:  # noqa: BLE001
            pass
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def last_weekday(d: date) -> date:
    """週末往前移至週五；平日原樣回傳。"""
    wd = d.weekday()
    if wd == 5:  # Saturday
        return d - timedelta(days=1)
    if wd == 6:  # Sunday
        return d - timedelta(days=2)
    return d


def business_days_between(older: date, newer: date) -> int:
    """計算 (older, newer] 之間的平日（週一～週五）天數。older >= newer 回 0。"""
    if older >= newer:
        return 0
    total_days = (newer - older).days
    full_weeks, rem = divmod(total_days, 7)
    count = full_weeks * 5
    start_wd = older.weekday()
    for offset in range(1, rem + 1):
        if (start_wd + offset) % 7 < 5:
            count += 1
    return count


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def ym_to_finmind_date(ym: Any) -> Optional[str]:
    """官方月營收資料年月 'YYYY-MM' → FinMind 月營收的 date（次月 1 日 'YYYY-MM-01'）。"""
    if not ym:
        return None
    s = str(ym).strip()
    if len(s) < 7 or s[4] != "-":
        return None
    try:
        y, m = int(s[:4]), int(s[5:7])
        if not 1 <= m <= 12:
            return None
        ny, nm = _shift_month(y, m, 1)
        return f"{ny:04d}-{nm:02d}-01"
    except ValueError:
        return None


def expected_latest_revenue_date(ref: date) -> date:
    """在參考日 ref 時，市場上應該已公布的最新月營收（對應 FinMind 的次月 1 日）。

    法定公告日為次月 10 日（遇假日順延最多至 12～13 日，再留 1 日排程同步緩衝）：
    - ref.day >= 15：上個月營收應已入庫（FinMind date = 本月 1 日）
    - ref.day < 15 ：上個月營收可能尚未公布，僅要求到上上個月（FinMind date = 上月 1 日）
    """
    if ref.day >= 15:
        return date(ref.year, ref.month, 1)
    py, pm = _shift_month(ref.year, ref.month, -1)
    return date(py, pm, 1)


def is_daily_covered(
    dates: list[str],
    start: str,
    end: str,
    *,
    today: Optional[date] = None,
    has_earlier: bool = False,
    has_later: bool = False,
) -> bool:
    """判斷日頻資料是否完整涵蓋請求區間 [start, end] 且夠新。"""
    if not dates:
        return False
    start_d = parse_iso_date(start)
    end_d = parse_iso_date(end)
    if start_d is None or end_d is None or start_d > end_d:
        return False

    parsed = [d for d in (parse_iso_date(x) for x in dates) if d is not None]
    if not parsed:
        return False
    min_d, max_d = min(parsed), max(parsed)

    # 1. 起點涵蓋
    span = (end_d - start_d).days
    start_slack = DAILY_START_SLACK_LONG if (has_earlier or span >= 30) else DAILY_START_SLACK_SHORT
    if (min_d - start_d).days > start_slack:
        return False

    # 2. 終點新鮮度
    if has_later:
        return True
    ref_today = today or od.tw_today()
    target = min(end_d, ref_today)
    effective_target = last_weekday(target)
    if business_days_between(max_d, effective_target) > DAILY_END_SLACK_BDAYS:
        return False
    return True


def is_monthly_covered(
    dates: list[str],
    start: str,
    end: str,
    *,
    today: Optional[date] = None,
    has_earlier: bool = False,
    has_later: bool = False,
) -> bool:
    """判斷月營收資料是否完整涵蓋請求區間 [start, end] 且夠新。"""
    if not dates:
        return False
    start_d = parse_iso_date(start)
    end_d = parse_iso_date(end)
    if start_d is None or end_d is None or start_d > end_d:
        return False

    parsed = [d for d in (parse_iso_date(x) for x in dates) if d is not None]
    if not parsed:
        return False
    min_d, max_d = min(parsed), max(parsed)

    # 1. 起點涵蓋（月資料每月一筆，允許最多 45 天偏移）
    if (min_d - start_d).days > MONTHLY_START_SLACK_DAYS:
        return False

    # 2. 終點新鮮度
    if has_later:
        return True
    ref_today = today or od.tw_today()
    target = min(end_d, ref_today)
    expected_end = expected_latest_revenue_date(target)
    if expected_end >= start_d and max_d < expected_end:
        return False
    return True


# ───────────────────────── 純函式：轉換為 FinMind 格式 ─────────────────────────

def _clean_md_record(doc: dict[str, Any]) -> dict[str, Any]:
    """md_* 文件 → 還原為 FinMind 原始列（symbol → stock_id，移除 updated_at/_id）。"""
    out = {k: v for k, v in doc.items() if k not in ("_id", "symbol", "updated_at")}
    if "symbol" in doc and "stock_id" not in out:
        out["stock_id"] = doc["symbol"]
    return out


def _is_finite_num(v: Any) -> bool:
    if v is None or isinstance(v, bool):
        return False
    try:
        f = float(v)
        return not (math.isnan(f) or math.isinf(f))
    except (TypeError, ValueError):
        return False


def md_price_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """md_price → 與 FinMindClient.get_stock_price() 100% 相容的 DataFrame。"""
    if not rows:
        return pd.DataFrame()
    cols = ["date", "open", "high", "low", "close", "volume"]
    cleaned = []
    for r in rows:
        d = r.get("date")
        if not d or not all(_is_finite_num(r.get(c)) for c in ("open", "high", "low", "close", "volume")):
            continue
        cleaned.append({
            "date": str(d)[:10],
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"]),
        })
    if not cleaned:
        return pd.DataFrame()
    df = pd.DataFrame(cleaned)[cols]
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return df


def md_institutional_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """md_institutional → 與 FinMindClient.get_institutional_investors() 相容的 DataFrame。"""
    if not rows:
        return pd.DataFrame()
    records = [_clean_md_record(r) for r in rows if r.get("date") and r.get("name")]
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    sort_cols = [c for c in ("date", "name") if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    return df


def _order_margin_df(df: pd.DataFrame) -> pd.DataFrame:
    """確保融資融券 DataFrame 欄位順序安全（YesterdayBalance 在 TodayBalance 之前）。"""
    ordered = [c for c in _MARGIN_COLUMNS if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    df = df[ordered + extra]
    if "date" in df.columns:
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return df


def md_margin_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """md_margin → 與 FinMindClient.get_margin_trading() 相容的 DataFrame。"""
    if not rows:
        return pd.DataFrame()
    records = [_clean_md_record(r) for r in rows if r.get("date")]
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "MarginPurchaseTodayBalance" not in df.columns or "ShortSaleTodayBalance" not in df.columns:
        return pd.DataFrame()
    return _order_margin_df(df)


def od_margin_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """od_margin（官方全市場融資融券，單位：張）→ 與 FinMindClient.get_margin_trading() 100% 相容。"""
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        d, sym = r.get("date"), r.get("symbol")
        if not d or not sym:
            continue
        records.append({
            "date": str(d)[:10],
            "stock_id": str(sym),
            "MarginPurchaseBuy": r.get("margin_buy") or 0,
            "MarginPurchaseCashRepayment": r.get("margin_repay") or 0,
            "MarginPurchaseLimit": r.get("margin_limit") or 0,
            "MarginPurchaseSell": r.get("margin_sell") or 0,
            "MarginPurchaseYesterdayBalance": r.get("margin_prev") or 0,
            "MarginPurchaseTodayBalance": r.get("margin_bal") or 0,
            "OffsetLoanAndShort": r.get("offset") or 0,
            "ShortSaleBuy": r.get("short_cover") or 0,
            "ShortSaleCashRepayment": r.get("short_repay") or 0,
            "ShortSaleLimit": r.get("short_limit") or 0,
            "ShortSaleSell": r.get("short_sell") or 0,
            "ShortSaleYesterdayBalance": r.get("short_prev") or 0,
            "ShortSaleTodayBalance": r.get("short_bal") or 0,
            "Note": "",
        })
    if not records:
        return pd.DataFrame()
    return _order_margin_df(pd.DataFrame(records))


def md_valuation_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """md_valuation → 與 FinMindClient.get_valuation() 相容的 DataFrame。"""
    if not rows:
        return pd.DataFrame()
    records = [_clean_md_record(r) for r in rows if r.get("date")]
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if not {"date", "PER", "PBR"} <= set(df.columns):
        return pd.DataFrame()
    return df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def od_valuation_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """od_valuation（官方全市場估值）→ 與 FinMindClient.get_valuation() 100% 相容。"""
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        d, sym = r.get("date"), r.get("symbol")
        if not d or not sym:
            continue
        records.append({
            "date": str(d)[:10],
            "stock_id": str(sym),
            "dividend_yield": r.get("dy"),
            "PER": r.get("pe"),
            "PBR": r.get("pb"),
        })
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    return df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def md_revenue_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """md_revenue → 與 FinMindClient.get_monthly_revenue() 相容的 DataFrame。"""
    if not rows:
        return pd.DataFrame()
    records = [_clean_md_record(r) for r in rows if r.get("date")]
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if not {"date", "revenue", "revenue_year", "revenue_month"} <= set(df.columns):
        return pd.DataFrame()
    return df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def od_revenue_to_df(
    rows: list[dict[str, Any]],
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """od_revenue（官方全市場月營收，單位：千元）→ 與 FinMindClient.get_monthly_revenue()（單位：元）100% 相容。"""
    if not rows:
        return pd.DataFrame()
    start_s = str(start)[:10] if start else None
    end_s = str(end)[:10] if end else None
    records = []
    for r in rows:
        ym = r.get("ym")
        sym = r.get("symbol")
        rev = r.get("rev")
        fm_date = ym_to_finmind_date(ym)
        if not fm_date or not sym or not _is_finite_num(rev):
            continue
        if start_s and fm_date < start_s:
            continue
        if end_s and fm_date > end_s:
            continue
        records.append({
            "date": fm_date,
            "stock_id": str(sym),
            "country": "Taiwan",
            # 官方開放資料月營收單位為「千元」，FinMind 為「元」，需乘以 1000
            "revenue": float(rev) * 1000.0,
            "revenue_month": int(str(ym)[5:7]),
            "revenue_year": int(str(ym)[:4]),
            "create_time": r.get("report_date") or "",
        })
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    return df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def _merge_by_date(primary: pd.DataFrame, secondary: pd.DataFrame) -> pd.DataFrame:
    """依 date 合併主源（md_*）與副源（od_*）；同日優先保留主源，並按 date 升冪排序。"""
    if primary is None or primary.empty:
        return secondary if secondary is not None else pd.DataFrame()
    if secondary is None or secondary.empty:
        return primary
    primary_dates = set(primary["date"].astype(str).str[:10])
    extra = secondary[~secondary["date"].astype(str).str[:10].isin(primary_dates)]
    if extra.empty:
        return primary
    merged = pd.concat([primary, extra], ignore_index=True)
    return merged.sort_values("date").reset_index(drop=True)


# ───────────────────────── 內部資料庫查詢協調 ─────────────────────────

def _ym_query_bounds(start: str, end: str) -> tuple[Optional[str], Optional[str]]:
    """將 FinMind 的 date 查詢範圍轉為 od_revenue 的 ym 查詢範圍（寬查再精準過濾）。"""
    sd = parse_iso_date(start)
    ed = parse_iso_date(end)
    ym_start = None
    ym_end = None
    if sd is not None:
        sy, sm = _shift_month(sd.year, sd.month, -1)
        ym_start = f"{sy:04d}-{sm:02d}"
    if ed is not None:
        ey, em = _shift_month(ed.year, ed.month, -1)
        ym_end = f"{ey:04d}-{em:02d}"
    return ym_start, ym_end


async def _check_md_daily_coverage(
    dataset: str,
    sym: str,
    dates: list[str],
    start: str,
    end: str,
    *,
    db,
    today: Optional[date],
) -> tuple[bool, bool, bool]:
    """檢查日頻涵蓋；僅在邊界曖昧時額外查一次 has_record_outside，省下多餘 DB 查詢。"""
    if is_daily_covered(dates, start, end, today=today):
        return (True, False, False)
    has_earlier, has_later = await st.has_record_outside(
        dataset, sym, before=start, after=end, db=db
    )
    ok = is_daily_covered(
        dates, start, end, today=today, has_earlier=has_earlier, has_later=has_later
    )
    return (ok, has_earlier, has_later)


async def _check_od_daily_coverage(
    dataset: str,
    sym: str,
    dates: list[str],
    start: str,
    end: str,
    *,
    db,
    today: Optional[date],
) -> tuple[bool, bool, bool]:
    if is_daily_covered(dates, start, end, today=today):
        return (True, False, False)
    has_earlier, has_later = await od.has_record_outside(
        dataset, sym, before=start, after=end, db=db
    )
    ok = is_daily_covered(
        dates, start, end, today=today, has_earlier=has_earlier, has_later=has_later
    )
    return (ok, has_earlier, has_later)


async def _run_db_read(
    coro_factory,
    *,
    db=None,
    label: str,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """統一執行本地讀庫：加逾時、安全捕捉所有 DB 異常、真實 DB 失敗時短暫冷卻。"""
    global _db_cooldown_until
    if db is None and time.monotonic() < _db_cooldown_until:
        return (None, None)
    try:
        return await asyncio.wait_for(coro_factory(), timeout=DB_READ_TIMEOUT_SEC)
    except Exception as exc:  # noqa: BLE001
        if db is None:
            _db_cooldown_until = time.monotonic() + DB_ERROR_COOLDOWN_SEC
        logger.warning("db_reader: %s 讀庫失敗，回落 FinMind（%s: %s）", label, type(exc).__name__, exc)
        return (None, None)


# ───────────────────────── 對外高階查詢介面 ─────────────────────────

async def read_stock_price_with_source(
    symbol: str,
    start: str,
    end: str,
    *,
    db=None,
    today: Optional[date] = None,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """優先讀 md_price；命中回 (DataFrame, 'md_price')，否則 (None, None)。"""
    sym = _normalize_query_symbol(symbol)
    if not sym:
        return (None, None)

    async def _op():
        rows = await st.query_dataset("price", sym, start, end, db=db)
        df = md_price_to_df(rows)
        if df.empty:
            return (None, None)
        dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
        ok, _, _ = await _check_md_daily_coverage("price", sym, dates, start, end, db=db, today=today)
        return (df, "md_price") if ok else (None, None)

    return await _run_db_read(_op, db=db, label=f"price/{sym}")


async def read_institutional_with_source(
    symbol: str,
    start: str,
    end: str,
    *,
    db=None,
    today: Optional[date] = None,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """優先讀 md_institutional；命中回 (DataFrame, 'md_institutional')，否則 (None, None)。"""
    sym = _normalize_query_symbol(symbol)
    if not sym:
        return (None, None)

    async def _op():
        rows = await st.query_dataset("institutional", sym, start, end, db=db)
        df = md_institutional_to_df(rows)
        if df.empty:
            return (None, None)
        dates = df["date"].astype(str).str[:10].tolist()
        ok, _, _ = await _check_md_daily_coverage("institutional", sym, dates, start, end, db=db, today=today)
        return (df, "md_institutional") if ok else (None, None)

    return await _run_db_read(_op, db=db, label=f"institutional/{sym}")


async def _read_dual_daily(
    dataset: str,
    md_conv,
    od_conv,
    symbol: str,
    start: str,
    end: str,
    *,
    db=None,
    today: Optional[date] = None,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """先讀 md_<dataset>；不足或無資料再讀 od_<dataset>，並支援依日期互補合併。"""
    sym = _normalize_query_symbol(symbol)
    if not sym:
        return (None, None)

    async def _op():
        md_rows = await st.query_dataset(dataset, sym, start, end, db=db)
        md_df = md_conv(md_rows)
        md_earlier = md_later = False
        if not md_df.empty:
            md_dates = md_df["date"].astype(str).str[:10].tolist()
            ok, md_earlier, md_later = await _check_md_daily_coverage(
                dataset, sym, md_dates, start, end, db=db, today=today
            )
            if ok:
                return (md_df, f"md_{dataset}")

        od_rows = await od.query_dataset(dataset, sym, start, end, db=db)
        od_df = od_conv(od_rows)
        if od_df.empty:
            return (None, None)

        od_dates = od_df["date"].astype(str).str[:10].tolist()
        if md_df.empty:
            ok, _, _ = await _check_od_daily_coverage(
                dataset, sym, od_dates, start, end, db=db, today=today
            )
            return (od_df, f"od_{dataset}") if ok else (None, None)

        # md_* 與 od_* 皆有資料：合併互補（同日以 md_* 為主）
        merged = _merge_by_date(md_df, od_df)
        merged_dates = merged["date"].astype(str).str[:10].tolist()
        if is_daily_covered(
            merged_dates, start, end, today=today, has_earlier=md_earlier, has_later=md_later
        ):
            return (merged, f"md+od_{dataset}")

        od_earlier, od_later = await od.has_record_outside(
            dataset, sym, before=start, after=end, db=db
        )
        if is_daily_covered(
            merged_dates,
            start,
            end,
            today=today,
            has_earlier=(md_earlier or od_earlier),
            has_later=(md_later or od_later),
        ):
            return (merged, f"md+od_{dataset}")
        return (None, None)

    return await _run_db_read(_op, db=db, label=f"{dataset}/{sym}")


async def read_margin_trading_with_source(
    symbol: str,
    start: str,
    end: str,
    *,
    db=None,
    today: Optional[date] = None,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """優先讀 md_margin，其次 od_margin（可互補合併）。"""
    df, src = await _read_dual_daily(
        "margin", md_margin_to_df, od_margin_to_df, symbol, start, end, db=db, today=today
    )
    if df is not None and not df.empty:
        df = _order_margin_df(df)
    return (df, src)


async def read_valuation_with_source(
    symbol: str,
    start: str,
    end: str,
    *,
    db=None,
    today: Optional[date] = None,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """優先讀 md_valuation，其次 od_valuation（可互補合併）。"""
    return await _read_dual_daily(
        "valuation", md_valuation_to_df, od_valuation_to_df, symbol, start, end, db=db, today=today
    )


async def read_monthly_revenue_with_source(
    symbol: str,
    start: str,
    end: str,
    *,
    db=None,
    today: Optional[date] = None,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """優先讀 md_revenue，其次 od_revenue（可互補合併，自動將千元轉元）。"""
    sym = _normalize_query_symbol(symbol)
    if not sym:
        return (None, None)

    async def _op():
        md_rows = await st.query_dataset("revenue", sym, start, end, db=db)
        md_df = md_revenue_to_df(md_rows)
        md_earlier = md_later = False
        if not md_df.empty:
            md_dates = md_df["date"].astype(str).str[:10].tolist()
            if is_monthly_covered(md_dates, start, end, today=today):
                return (md_df, "md_revenue")
            md_earlier, md_later = await st.has_record_outside(
                "revenue", sym, before=start, after=end, db=db
            )
            if is_monthly_covered(
                md_dates, start, end, today=today, has_earlier=md_earlier, has_later=md_later
            ):
                return (md_df, "md_revenue")

        ym_start, ym_end = _ym_query_bounds(start, end)
        od_rows = await od.query_dataset("revenue", sym, ym_start, ym_end, db=db)
        od_df = od_revenue_to_df(od_rows, start=start, end=end)
        if od_df.empty:
            return (None, None)

        if md_df.empty:
            od_dates = od_df["date"].astype(str).str[:10].tolist()
            if is_monthly_covered(od_dates, start, end, today=today):
                return (od_df, "od_revenue")
            od_earlier, od_later = await od.has_record_outside(
                "revenue", sym, before=ym_start, after=ym_end, db=db
            )
            if is_monthly_covered(
                od_dates, start, end, today=today, has_earlier=od_earlier, has_later=od_later
            ):
                return (od_df, "od_revenue")
            return (None, None)

        merged = _merge_by_date(md_df, od_df)
        merged_dates = merged["date"].astype(str).str[:10].tolist()
        if is_monthly_covered(
            merged_dates, start, end, today=today, has_earlier=md_earlier, has_later=md_later
        ):
            return (merged, "md+od_revenue")
        od_earlier, od_later = await od.has_record_outside(
            "revenue", sym, before=ym_start, after=ym_end, db=db
        )
        if is_monthly_covered(
            merged_dates,
            start,
            end,
            today=today,
            has_earlier=(md_earlier or od_earlier),
            has_later=(md_later or od_later),
        ):
            return (merged, "md+od_revenue")
        return (None, None)

    return await _run_db_read(_op, db=db, label=f"revenue/{sym}")


# 簡化包裝（只取 DataFrame 或 None）
async def read_stock_price(symbol: str, start: str, end: str, *, db=None, today: Optional[date] = None) -> Optional[pd.DataFrame]:
    df, _ = await read_stock_price_with_source(symbol, start, end, db=db, today=today)
    return df


async def read_institutional_investors(symbol: str, start: str, end: str, *, db=None, today: Optional[date] = None) -> Optional[pd.DataFrame]:
    df, _ = await read_institutional_with_source(symbol, start, end, db=db, today=today)
    return df


async def read_margin_trading(symbol: str, start: str, end: str, *, db=None, today: Optional[date] = None) -> Optional[pd.DataFrame]:
    df, _ = await read_margin_trading_with_source(symbol, start, end, db=db, today=today)
    return df


async def read_valuation(symbol: str, start: str, end: str, *, db=None, today: Optional[date] = None) -> Optional[pd.DataFrame]:
    df, _ = await read_valuation_with_source(symbol, start, end, db=db, today=today)
    return df


async def read_monthly_revenue(symbol: str, start: str, end: str, *, db=None, today: Optional[date] = None) -> Optional[pd.DataFrame]:
    df, _ = await read_monthly_revenue_with_source(symbol, start, end, db=db, today=today)
    return df
