"""官方開放資料倉庫：每天把證交所、櫃買中心、集保的公開資料抓下來，存進自己的 MongoDB（od_* 集合）。

為什麼有這個模組
- 現有頁面每次都即時打 FinMind，額度（每小時 600 次）吃緊；集保（TDCC）的檔案又大又常連不上。
- 官方本來就公開這些資料。每天收盤後抓一次、存起來，之後頁面讀自己的資料庫，不佔 FinMind 額度，
  而且歷史會一天一天累積（官方多半只給「最新一份」）。

守則（寫在程式裡，不只是文件）
- 只打官方開放資料接口（證交所／櫃買 OpenAPI、集保開放資料），不爬網頁、不碰要驗證碼的頁面
  （例如券商分點）。證交所網頁版 JSON（rwd）只用在融資融券：開放資料版沒有日期欄位，會把昨天的資料標成今天。
- 誠實的 User-Agent、請求間隔至少 1 秒、每天只跑一次；失敗最多重試 2 次。
- 被擋（HTTP 403／429／防火牆頁）就立刻停止整輪並冷卻 6 小時，絕不嘗試繞過。
- 網址轉址或 404 不跟隨、直接報錯（舊網址「默默轉走」正是爬蟲常見的壞法）；欄位少了、筆數太少也報錯、不寫入。
- 先建唯一索引再 upsert（沒索引的 upsert 每筆都全表掃描，O(n²)）；重跑不會產生重複資料。

純函式（解析、日期與數字轉換、健康判斷）不碰網路與資料庫，方便單元測試；
run_sync 的 db 與 client 可注入，測試用假的。
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

UA = "finlab-stock-analyzer/1.0 (personal research; once-daily; low rate)"
MIN_GAP_SEC = 1.0  # 任兩個請求之間至少隔這麼久
TIMEOUT_SEC = 60.0  # 櫃買的檔案約 5 MB，實測 6～9 秒
RETRIES = 2
RETRY_BACKOFF_SEC = 3.0
COOL_OFF_HOURS = 6
MARGIN_LOOKBACK_WEEKDAYS = 5  # 證交所融資融券：往前看幾個平日，補上缺的日期
TDCC_MIN_GAP_DAYS = 7  # 集保每週一份（資料日為週五）；已存的最新一份不到 7 天就不重抓
RUNS_KEEP = 60

STATE_COLL = "od_state"
RUNS_COLL = "od_runs"
META_ID = "_meta"
_TW = timezone(timedelta(hours=8))

_run_lock = asyncio.Lock()
_running = False


class OpenDataError(Exception):
    """抓取或解析失敗（會記進執行紀錄，不影響其他來源）。"""


class BlockedError(OpenDataError):
    """被來源擋下（403／429／防火牆頁）。整輪停止並冷卻，不重試、不繞過。"""


class SchemaError(OpenDataError):
    """格式變了：欄位不見、筆數異常少、日期無法判讀。不寫入任何資料。"""


class FetchError(OpenDataError):
    """連線失敗、5xx、404、轉址。"""


# ───────────────────────── 來源與資料集 ─────────────────────────

@dataclass(frozen=True)
class Source:
    name: str
    dataset: str
    mkt: str
    url: str
    kind: str  # json | csv | twse_margin
    min_rows: int  # 解析後至少要有幾筆，否則視為格式異常（0 = 允許空，例如當天沒有處置股）


_TWSE = "https://openapi.twse.com.tw/v1"
_TPEX = "https://www.tpex.org.tw/openapi/v1"

SOURCES: list[Source] = [
    Source("twse_margin", "margin", "twse", "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN", "twse_margin", 800),
    Source("tpex_margin", "margin", "tpex", f"{_TPEX}/tpex_mainboard_margin_balance", "json", 400),
    Source("twse_valuation", "valuation", "twse", f"{_TWSE}/exchangeReport/BWIBBU_ALL", "json", 600),
    Source("tpex_valuation", "valuation", "tpex", f"{_TPEX}/tpex_mainboard_peratio_analysis", "json", 400),
    Source("twse_revenue", "revenue", "twse", f"{_TWSE}/opendata/t187ap05_L", "json", 50),
    Source("tpex_revenue", "revenue", "tpex", f"{_TPEX}/mopsfin_t187ap05_O", "json", 50),
    Source("twse_disposal", "disposal", "twse", f"{_TWSE}/announcement/punish", "json", 0),
    Source("tpex_disposal", "disposal", "tpex", f"{_TPEX}/tpex_disposal_information", "json", 0),
    Source("twse_attention", "attention", "twse", f"{_TWSE}/announcement/notice", "json", 0),
    Source("tpex_attention", "attention", "tpex", f"{_TPEX}/tpex_trading_warning_information", "json", 0),
    Source("tdcc_dist", "tdcc", "tdcc", "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5", "csv", 2000),
]

# 每個資料集：collection、唯一鍵、日期欄位、額外索引、健康判斷（success_days＝多久沒成功算過期；data_days＝資料日期落後多少天算過期）
DATASETS: dict[str, dict[str, Any]] = {
    "margin": {"coll": "od_margin", "keys": ("symbol", "date"), "date_field": "date", "label": "融資融券（上市＋上櫃）", "success_days": 3, "data_days": 5},
    "valuation": {"coll": "od_valuation", "keys": ("symbol", "date"), "date_field": "date", "label": "本益比／淨值比／殖利率", "success_days": 3, "data_days": 5},
    "revenue": {"coll": "od_revenue", "keys": ("symbol", "ym"), "date_field": "ym", "label": "月營收", "success_days": 3, "data_days": None},
    "disposal": {"coll": "od_disposal", "keys": ("symbol", "date", "start"), "date_field": "date", "label": "處置股公告", "success_days": 3, "data_days": None},
    "attention": {"coll": "od_attention", "keys": ("symbol", "date"), "date_field": "date", "label": "注意股公告", "success_days": 3, "data_days": None},
    "tdcc": {"coll": "od_tdcc", "keys": ("symbol", "date"), "date_field": "date", "label": "集保股權分散表（每週）", "success_days": 3, "data_days": 14},
}


# ───────────────────────── 日期與數字 ─────────────────────────

def tw_today() -> date:
    return datetime.now(_TW).date()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # 與 Mongo 讀回來的 naive UTC 一致


def roc_to_iso(value: Any) -> Optional[str]:
    """民國 '1151112'／'115/11/09'、西元 '20261106'／'2026-11-12' → 'YYYY-MM-DD'；看不懂回 None。"""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    try:
        if len(digits) == 8:
            y, m, d = int(digits[:4]), int(digits[4:6]), int(digits[6:])
        elif len(digits) in (6, 7):
            y, m, d = int(digits[:-4]) + 1911, int(digits[-4:-2]), int(digits[-2:])
        else:
            return None
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def roc_ym(value: Any) -> Optional[str]:
    """資料年月：民國 '11510'、西元 '202610' → '2026-10'。"""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    try:
        if len(digits) == 6:
            y, m = int(digits[:4]), int(digits[4:])
        elif len(digits) in (4, 5):
            y, m = int(digits[:-2]) + 1911, int(digits[-2:])
        else:
            return None
        if not 1 <= m <= 12:
            return None
        return f"{y:04d}-{m:02d}"
    except ValueError:
        return None


_EMPTY_NUM = {"", "-", "--", "---", "N/A", "NA", "X", "x"}


def to_num(value: Any, integer: bool = False) -> Optional[float | int]:
    """'1,234'、' 12.5 ' → 數字；空白、'-'、'N/A' → None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
    else:
        s = str(value).strip().replace(",", "")
        if s in _EMPTY_NUM:
            return None
        try:
            f = float(s)
        except ValueError:
            return None
        if not integer and re.fullmatch(r"[+-]?\d+", s):
            return int(s)
    if math.isnan(f) or math.isinf(f):
        return None
    return int(round(f)) if integer else (int(f) if f.is_integer() else f)


_SYMBOL_RE = re.compile(r"^[0-9A-Z]{2,10}$")


def clean_symbol(value: Any) -> Optional[str]:
    s = str(value or "").strip().upper()
    return s if _SYMBOL_RE.match(s) else None


def _need(row: dict, fields: list[str], source: str) -> None:
    missing = [f for f in fields if f not in row]
    if missing:
        raise SchemaError(f"{source}：欄位不見了 {missing}（來源格式可能改版）")


# ───────────────────────── 解析（純函式） ─────────────────────────

def parse_twse_margin(payload: dict) -> tuple[Optional[str], list[dict]]:
    """證交所網頁版 JSON（MI_MARGN）→ (資料日期, 文件)。以欄位數與第一欄名稱確認格式，不靠表格順序。"""
    d = roc_to_iso(payload.get("date"))
    if not d:
        raise SchemaError("twse_margin：回應沒有可判讀的日期")
    table = next((t for t in payload.get("tables", []) if t.get("fields") and len(t["fields"]) == 16 and t["fields"][0] == "代號"), None)
    if table is None:
        raise SchemaError("twse_margin：找不到「融資融券彙總」表（欄位數或名稱變了）")
    docs: list[dict] = []
    for r in table.get("data", []):
        sym = clean_symbol(r[0]) if r else None
        if not sym or len(r) < 15:
            continue
        docs.append({
            "mkt": "twse", "symbol": sym, "date": d,
            "margin_buy": to_num(r[2], True), "margin_sell": to_num(r[3], True), "margin_repay": to_num(r[4], True),
            "margin_prev": to_num(r[5], True), "margin_bal": to_num(r[6], True), "margin_limit": to_num(r[7], True),
            "short_cover": to_num(r[8], True), "short_sell": to_num(r[9], True), "short_repay": to_num(r[10], True),
            "short_prev": to_num(r[11], True), "short_bal": to_num(r[12], True), "short_limit": to_num(r[13], True),
            "offset": to_num(r[14], True),
        })
    return d, docs


def parse_tpex_margin(rows: list[dict]) -> list[dict]:
    if rows:
        _need(rows[0], ["Date", "SecuritiesCompanyCode", "MarginPurchaseBalance", "ShortSaleBalance"], "tpex_margin")
    docs = []
    for r in rows:
        sym, d = clean_symbol(r.get("SecuritiesCompanyCode")), roc_to_iso(r.get("Date"))
        if not sym or not d:
            continue
        docs.append({
            "mkt": "tpex", "symbol": sym, "date": d,
            "margin_buy": to_num(r.get("MarginPurchase"), True), "margin_sell": to_num(r.get("MarginSales"), True),
            "margin_repay": to_num(r.get("CashRedemption"), True), "margin_prev": to_num(r.get("MarginPurchaseBalancePreviousDay"), True),
            "margin_bal": to_num(r.get("MarginPurchaseBalance"), True), "margin_limit": to_num(r.get("MarginPurchaseQuota"), True),
            "short_cover": to_num(r.get("ShortConvering"), True), "short_sell": to_num(r.get("ShortSale"), True),
            "short_repay": to_num(r.get("StockRedemption"), True), "short_prev": to_num(r.get("ShortSaleBalancePreviousDay"), True),
            "short_bal": to_num(r.get("ShortSaleBalance"), True), "short_limit": to_num(r.get("ShortSaleQuota"), True),
            "offset": to_num(r.get("Offsetting"), True),
        })
    return docs


def parse_twse_valuation(rows: list[dict]) -> list[dict]:
    if rows:
        _need(rows[0], ["Date", "Code", "PEratio", "PBratio", "DividendYield"], "twse_valuation")
    docs = []
    for r in rows:
        sym, d = clean_symbol(r.get("Code")), roc_to_iso(r.get("Date"))
        if sym and d:
            docs.append({"mkt": "twse", "symbol": sym, "date": d, "pe": to_num(r.get("PEratio")), "pb": to_num(r.get("PBratio")), "dy": to_num(r.get("DividendYield"))})
    return docs


def parse_tpex_valuation(rows: list[dict]) -> list[dict]:
    if rows:
        _need(rows[0], ["Date", "SecuritiesCompanyCode", "PriceEarningRatio", "PriceBookRatio", "YieldRatio"], "tpex_valuation")
    docs = []
    for r in rows:
        sym, d = clean_symbol(r.get("SecuritiesCompanyCode")), roc_to_iso(r.get("Date"))
        if sym and d:
            docs.append({"mkt": "tpex", "symbol": sym, "date": d, "pe": to_num(r.get("PriceEarningRatio")), "pb": to_num(r.get("PriceBookRatio")), "dy": to_num(r.get("YieldRatio")), "dps": to_num(r.get("DividendPerShare"))})
    return docs


_REV_FIELDS = ["出表日期", "資料年月", "公司代號", "營業收入-當月營收", "營業收入-去年同月增減(%)"]


def _parse_revenue(rows: list[dict], mkt: str, source: str) -> list[dict]:
    if rows:
        _need(rows[0], _REV_FIELDS, source)
    docs = []
    for r in rows:
        sym, ym = clean_symbol(r.get("公司代號")), roc_ym(r.get("資料年月"))
        if not sym or not ym:
            continue
        docs.append({
            "mkt": mkt, "symbol": sym, "ym": ym, "report_date": roc_to_iso(r.get("出表日期")),
            "industry": (r.get("產業別") or "").strip() or None,
            "rev": to_num(r.get("營業收入-當月營收")), "rev_prev_month": to_num(r.get("營業收入-上月營收")),
            "rev_prev_year": to_num(r.get("營業收入-去年當月營收")),
            "mom": to_num(r.get("營業收入-上月比較增減(%)")), "yoy": to_num(r.get("營業收入-去年同月增減(%)")),
            "cum": to_num(r.get("累計營業收入-當月累計營收")), "cum_prev_year": to_num(r.get("累計營業收入-去年累計營收")),
            "cum_yoy": to_num(r.get("累計營業收入-前期比較增減(%)")),
            "note": (r.get("備註") or "").strip().strip("-") or None,
        })
    return docs


def parse_twse_revenue(rows: list[dict]) -> list[dict]:
    return _parse_revenue(rows, "twse", "twse_revenue")


def parse_tpex_revenue(rows: list[dict]) -> list[dict]:
    return _parse_revenue(rows, "tpex", "tpex_revenue")


def _period(text: Any) -> tuple[Optional[str], Optional[str]]:
    """'115/11/09～115/11/13'、'1151112~1151118' → (起, 迄) ISO。"""
    parts = re.split(r"[~～]", str(text or ""))
    start = roc_to_iso(parts[0]) if parts else None
    end = roc_to_iso(parts[1]) if len(parts) > 1 else None
    return start, end


def parse_twse_disposal(rows: list[dict]) -> list[dict]:
    if rows:
        _need(rows[0], ["Code", "Date", "DispositionPeriod", "ReasonsOfDisposition"], "twse_disposal")
    docs = []
    for r in rows:
        sym, d = clean_symbol(r.get("Code")), roc_to_iso(r.get("Date"))
        start, end = _period(r.get("DispositionPeriod"))
        if not sym or not d or not start:
            continue
        docs.append({
            "mkt": "twse", "symbol": sym, "name": (r.get("Name") or "").strip(), "date": d, "start": start, "end": end,
            "reason": (r.get("ReasonsOfDisposition") or "").strip(), "measures": (r.get("DispositionMeasures") or "").strip(),
            "times": to_num(r.get("NumberOfAnnouncement"), True), "detail": (r.get("Detail") or "").strip()[:2000],
        })
    return docs


def parse_tpex_disposal(rows: list[dict]) -> list[dict]:
    if rows:
        _need(rows[0], ["SecuritiesCompanyCode", "Date", "DispositionPeriod", "DispositionReasons"], "tpex_disposal")
    docs = []
    for r in rows:
        sym, d = clean_symbol(r.get("SecuritiesCompanyCode")), roc_to_iso(r.get("Date"))
        start, end = _period(r.get("DispositionPeriod"))
        if not sym or not d or not start:
            continue
        docs.append({
            "mkt": "tpex", "symbol": sym, "name": (r.get("CompanyName") or "").strip(), "date": d, "start": start, "end": end,
            "reason": (r.get("DispositionReasons") or "").strip(), "measures": "", "times": None,
            "detail": (r.get("DisposalCondition") or "").strip()[:2000],
        })
    return docs


def parse_twse_attention(rows: list[dict]) -> list[dict]:
    if rows:
        _need(rows[0], ["Code", "Date", "TradingInfoForAttention"], "twse_attention")
    docs = []
    for r in rows:  # 當天沒有注意股時，來源會回一列代號空白的假資料，這裡會被濾掉
        sym, d = clean_symbol(r.get("Code")), roc_to_iso(r.get("Date"))
        if sym and d:
            docs.append({"mkt": "twse", "symbol": sym, "name": (r.get("Name") or "").strip(), "date": d, "info": (r.get("TradingInfoForAttention") or "").strip(), "times": to_num(r.get("NumberOfAnnouncement"), True), "close": to_num(r.get("ClosingPrice")), "pe": to_num(r.get("PE"))})
    return docs


def parse_tpex_attention(rows: list[dict]) -> list[dict]:
    if rows:
        _need(rows[0], ["SecuritiesCompanyCode", "Date", "TradingInformation"], "tpex_attention")
    docs = []
    for r in rows:
        sym, d = clean_symbol(r.get("SecuritiesCompanyCode")), roc_to_iso(r.get("Date"))
        if sym and d:
            docs.append({"mkt": "tpex", "symbol": sym, "name": (r.get("CompanyName") or "").strip(), "date": d, "info": (r.get("TradingInformation") or "").strip(), "times": None, "close": to_num(r.get("ClosePrice")), "pe": to_num(r.get("PriceEarningRatio"))})
    return docs


def parse_tdcc(text: str) -> list[dict]:
    """集保股權分散表 CSV（每檔 17 列）→ 每檔一份文件。

    lv：第 1～15 級的 [人數, 股數, 占集保庫存%]（第 12～15 級＝400 張以上，第 15 級＝1,000 張以上）；
    第 16 級為差異數調整（adj_shares）、第 17 級為合計（total_holders／total_shares）。
    """
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or len(header) < 6 or "代號" not in header[1] or "分級" not in header[2]:
        raise SchemaError(f"tdcc_dist：表頭不是預期的樣子：{header}")
    groups: dict[tuple[str, str], dict] = {}
    for r in reader:
        if len(r) < 6:
            continue
        d, sym, lvl = roc_to_iso(r[0]), clean_symbol(r[1]), to_num(r[2], True)
        if not d or not sym or lvl is None or not 1 <= lvl <= 17:
            continue
        g = groups.setdefault((d, sym), {"symbol": sym, "date": d, "lv": [None] * 15, "adj_shares": None, "total_holders": None, "total_shares": None})
        holders, shares, pct = to_num(r[3], True), to_num(r[4], True), to_num(r[5])
        if lvl <= 15:
            g["lv"][lvl - 1] = [holders, shares, pct]
        elif lvl == 16:
            g["adj_shares"] = shares
        else:
            g["total_holders"], g["total_shares"] = holders, shares
    docs = []
    for g in groups.values():
        big = [x for x in g["lv"][11:15] if x]
        top = g["lv"][14]
        g["pct_400plus"] = round(sum(x[2] or 0 for x in big), 2) if big else None
        g["holders_400plus"] = sum(x[0] or 0 for x in big) if big else None
        g["pct_1000plus"] = top[2] if top else None
        g["holders_1000plus"] = top[0] if top else None
        docs.append(g)
    return docs


PARSERS: dict[str, Callable[[Any], list[dict]]] = {
    "tpex_margin": parse_tpex_margin,
    "twse_valuation": parse_twse_valuation, "tpex_valuation": parse_tpex_valuation,
    "twse_revenue": parse_twse_revenue, "tpex_revenue": parse_tpex_revenue,
    "twse_disposal": parse_twse_disposal, "tpex_disposal": parse_tpex_disposal,
    "twse_attention": parse_twse_attention, "tpex_attention": parse_tpex_attention,
    "tdcc_dist": parse_tdcc,
}


def check_volume(src: Source, raw_count: int, docs: list[dict]) -> None:
    """筆數檢查：太少、或原始資料有、卻幾乎都解析不出來（欄位改名的典型症狀），一律不寫入。"""
    if len(docs) < src.min_rows:
        raise SchemaError(f"{src.name}：只解析出 {len(docs)} 筆（至少應有 {src.min_rows}），來源可能異常，這次不寫入")
    if raw_count >= 20 and len(docs) < raw_count * 0.8:
        raise SchemaError(f"{src.name}：{raw_count} 筆原始資料只解析出 {len(docs)} 筆，格式可能改版，這次不寫入")


# ───────────────────────── HTTP 客戶端 ─────────────────────────

_BLOCK_PAGE_RE = re.compile(r"FOR SECURITY REASONS|Access Denied|Request Rejected", re.IGNORECASE)
_BLOCK_STAT_RE = re.compile(r"頻繁|過多|限制|拒絕|封鎖|IP")


class OpenDataClient:
    """有禮貌的 HTTP 客戶端：誠實 UA、固定間隔、有限重試、被擋立刻停、不跟隨轉址。"""

    def __init__(
        self,
        min_gap: float = MIN_GAP_SEC,
        timeout: float = TIMEOUT_SEC,
        retries: int = RETRIES,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_gap, self.retries = min_gap, retries
        self._sleep, self._clock = sleep, clock
        self._last: Optional[float] = None
        self.requests = 0
        self._http = httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": UA, "Accept": "application/json, text/csv;q=0.9, */*;q=0.5"},
            follow_redirects=False, transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _throttle(self) -> None:
        if self._last is not None:
            wait = self._last + self.min_gap - self._clock()
            if wait > 0:
                await self._sleep(wait)
        self._last = self._clock()

    async def get(self, url: str, params: Optional[dict] = None) -> httpx.Response:
        parsed = urlparse(url)
        where = f"{parsed.netloc}{parsed.path}"
        last_err = ""
        for attempt in range(self.retries + 1):
            await self._throttle()
            self.requests += 1
            try:
                resp = await self._http.get(url, params=params)
            except httpx.HTTPError as exc:
                last_err = f"{type(exc).__name__}: {exc}"[:160]
            else:
                sc = resp.status_code
                if sc in (403, 429):
                    raise BlockedError(f"{where} 回應 HTTP {sc}（被擋或請求過多）")
                if 300 <= sc < 400:
                    raise FetchError(f"{where} 回應 HTTP {sc}，轉到 {resp.headers.get('location')}——網址可能已改版，沒有跟隨")
                if sc == 404:
                    raise FetchError(f"{where} 回應 404——網址可能已改版")
                if sc >= 500:
                    last_err = f"HTTP {sc}"
                elif sc >= 400:
                    raise FetchError(f"{where} 回應 HTTP {sc}")
                else:
                    return resp
            if attempt < self.retries:
                await self._sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        raise FetchError(f"{where} 連線失敗：{last_err}")

    async def get_json(self, url: str, params: Optional[dict] = None) -> Any:
        resp = await self.get(url, params)
        if _BLOCK_PAGE_RE.search(resp.text[:2000]):
            raise BlockedError(f"{urlparse(url).netloc} 回了防火牆頁面")
        try:
            return resp.json()
        except ValueError:
            raise SchemaError(f"{urlparse(url).netloc}{urlparse(url).path} 回應不是 JSON：{resp.text[:60]!r}") from None

    async def get_text(self, url: str, encoding: str = "utf-8-sig") -> str:
        resp = await self.get(url)
        text = resp.content.decode(encoding, errors="replace")
        if _BLOCK_PAGE_RE.search(text[:2000]):
            raise BlockedError(f"{urlparse(url).netloc} 回了防火牆頁面")
        return text


# ───────────────────────── 抓取 ─────────────────────────

@dataclass
class SourceResult:
    docs: list[dict]
    data_date: Optional[str] = None
    skipped: Optional[str] = None
    empty_dates: Optional[list[str]] = None


def recent_weekdays(today: date, n: int) -> list[date]:
    """含今天在內，往前數 n 個平日，由舊到新。"""
    out, d = [], today
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


async def pull_twse_margin(
    client: OpenDataClient, src: Source, today: date, known_dates: set[str], prev_empty: list[str]
) -> SourceResult:
    """證交所融資融券：逐日（帶日期參數）抓最近幾個平日裡還沒存過的日子。
    某天回「沒有符合條件的資料」＝假日或尚未公布；過去的日子記起來不再重問，今天的明天再試。"""
    docs: list[dict] = []
    empty = [d for d in prev_empty if d < today.isoformat()]
    newest: Optional[str] = None
    for d in recent_weekdays(today, MARGIN_LOOKBACK_WEEKDAYS):
        iso = d.isoformat()
        if iso in known_dates or iso in empty:
            continue
        payload = await client.get_json(src.url, {"date": d.strftime("%Y%m%d"), "selectType": "ALL", "response": "json"})
        stat = str(payload.get("stat", "")) if isinstance(payload, dict) else ""
        if stat == "OK":
            got_date, got = parse_twse_margin(payload)
            if got_date != iso:
                raise SchemaError(f"twse_margin：要求 {iso}，回應卻是 {got_date}")
            check_volume(src, len(got), got)
            docs += got
            newest = max(newest or iso, iso)
        elif "大於今日" in stat:
            continue  # 來源認為這天還沒到（時差）；不記為空，下次再問
        elif "沒有符合條件" in stat:
            if iso < today.isoformat():
                empty.append(iso)
        elif _BLOCK_STAT_RE.search(stat):
            raise BlockedError(f"twse_margin：來源訊息「{stat}」")
        else:
            raise SchemaError(f"twse_margin：不認得的回應狀態「{stat}」")
    return SourceResult(docs, data_date=newest, empty_dates=sorted(set(empty)))


async def pull_source(
    client: OpenDataClient, src: Source, today: date, known_dates: set[str], prev: dict, force: bool
) -> SourceResult:
    if src.kind == "twse_margin":
        return await pull_twse_margin(client, src, today, known_dates, list(prev.get("empty_dates") or []))
    if src.kind == "csv":
        latest = prev.get("data_date")
        if latest and not force:
            try:
                if (today - date.fromisoformat(latest)).days < TDCC_MIN_GAP_DAYS:
                    return SourceResult([], data_date=latest, skipped="fresh")
            except ValueError:
                pass
        text = await client.get_text(src.url)
        docs = PARSERS[src.name](text)
        check_volume(src, len(docs), docs)
        dates = {d["date"] for d in docs}
        return SourceResult(docs, data_date=max(dates) if dates else None)
    rows = await client.get_json(src.url)
    if not isinstance(rows, list):
        raise SchemaError(f"{src.name}：預期是清單，拿到 {type(rows).__name__}")
    docs = PARSERS[src.name](rows)
    check_volume(src, len(rows), docs)
    dates = [d["date"] for d in docs if d.get("date")] or [d["ym"] for d in docs if d.get("ym")]
    return SourceResult(docs, data_date=max(dates) if dates else None)


# ───────────────────────── 資料庫 ─────────────────────────

async def _db():
    from ..db.mongodb import get_mongodb

    return await get_mongodb()


async def ensure_indexes(db=None) -> None:
    db = db if db is not None else await _db()
    for spec in DATASETS.values():
        coll = db[spec["coll"]]
        await coll.create_index([(k, 1) for k in spec["keys"]], unique=True)  # 查單檔歷史＋upsert 用（symbol 在最前）
        await coll.create_index([(spec["date_field"], 1)])  # 查「某天全市場」用
    await db[RUNS_COLL].create_index([("started_at", -1)])


async def upsert_docs(coll, keys: tuple, docs: list[dict], first_seen: str, chunk: int = 2000) -> int:
    """依唯一鍵 upsert；文件內容沒變時 Mongo 不會真的寫入（所以不放更新時間戳記）。first_seen＝第一次抓到那天。"""
    from pymongo import UpdateOne

    n = 0
    for i in range(0, len(docs), chunk):
        part = docs[i:i + chunk]
        ops = [UpdateOne({k: d.get(k) for k in keys}, {"$set": d, "$setOnInsert": {"first_seen": first_seen}}, upsert=True) for d in part]
        await coll.bulk_write(ops, ordered=False)
        n += len(part)
    return n


async def _known_margin_dates(db, today: date) -> set[str]:
    since = (today - timedelta(days=MARGIN_LOOKBACK_WEEKDAYS * 2 + 4)).isoformat()
    got = await db[DATASETS["margin"]["coll"]].distinct("date", {"mkt": "twse", "date": {"$gte": since}})
    return set(got or [])


# ───────────────────────── 執行一輪 ─────────────────────────

def is_running() -> bool:
    return _running


async def _run_source(db, client, src: Source, ds_state: dict, today: date, force: bool, now: datetime) -> dict[str, Any]:
    spec = DATASETS[src.dataset]
    prev = (ds_state.get("sources") or {}).get(src.name, {})
    out: dict[str, Any] = {"ok": False, "rows": 0, "data_date": prev.get("data_date"), "error": None, "skipped": None, "at": now}
    if prev.get("empty_dates"):
        out["empty_dates"] = prev["empty_dates"]
    try:
        known = await _known_margin_dates(db, today) if src.kind == "twse_margin" else set()
        res = await pull_source(client, src, today, known, prev, force)
        out["rows"] = await upsert_docs(db[spec["coll"]], spec["keys"], res.docs, today.isoformat()) if res.docs else 0
        out["ok"], out["skipped"] = True, res.skipped
        out["data_date"] = res.data_date or prev.get("data_date")
        if res.empty_dates is not None:
            out["empty_dates"] = res.empty_dates
    except BlockedError:
        raise
    except Exception as exc:  # noqa: BLE001  一個來源失敗不影響其他來源
        logger.warning("open_data: %s 失敗：%s", src.name, exc)
        out["error"] = str(exc)[:300]
    return out


def _dataset_state(ds_state: dict, src_results: dict[str, dict], now: datetime, n_sources: int) -> dict[str, Any]:
    """這輪跑完後該寫進 od_state 的內容。只有「這個資料集的所有來源都成功」才更新 last_success_at
    （上市成功、上櫃失敗不算成功——少了半個市場的資料不能說是新鮮的）。"""
    oks = [r for r in src_results.values() if r["ok"]]
    errs = [f"{n}：{r['error']}" for n, r in src_results.items() if r["error"]]
    new = {
        "sources": {**(ds_state.get("sources") or {}), **src_results},
        "last_run_at": now, "last_error": "；".join(errs) if errs else None,
        "last_success_at": ds_state.get("last_success_at"), "last_data_date": ds_state.get("last_data_date"),
        "last_rows": ds_state.get("last_rows"),
    }
    if len(oks) == n_sources:
        new["last_success_at"] = now
        dates = [r["data_date"] for r in oks if r.get("data_date")]
        if dates:
            new["last_data_date"] = max(dates)
        new["last_rows"] = sum(r["rows"] for r in oks)
    return new


async def run_sync(
    datasets: Optional[list[str]] = None,
    trigger: str = "schedule",
    force: bool = False,
    db=None,
    client: Optional[OpenDataClient] = None,
    now: Optional[datetime] = None,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """跑一輪。同時只允許一輪；冷卻中回傳 skipped。回傳摘要（也會寫進 od_runs）。"""
    global _running
    if _run_lock.locked():
        return {"skipped": "already_running"}
    async with _run_lock:
        _running = True
        own_client = client is None
        try:
            db = db if db is not None else await _db()
            started = now or _utcnow()
            today = today or tw_today()
            meta = await db[STATE_COLL].find_one({"_id": META_ID}) or {}
            until = meta.get("blocked_until")
            if until and until > started:
                logger.warning("open_data: 冷卻中（來源先前擋過），%s 之前不抓", until)
                return {"skipped": "cooling_off", "blocked_until": until}

            await ensure_indexes(db)
            client = client or OpenDataClient()
            ds_list = [d for d in (datasets if datasets is not None else list(DATASETS)) if d in DATASETS]
            summary: dict[str, Any] = {"trigger": trigger, "started_at": started, "datasets": ds_list, "force": force,
                                       "sources": {}, "rows": 0, "errors": 0, "aborted": None, "requests": 0}
            try:
                for ds in ds_list:
                    ds_state = await db[STATE_COLL].find_one({"_id": ds}) or {}
                    results: dict[str, dict] = {}
                    srcs = [s for s in SOURCES if s.dataset == ds]
                    try:
                        for src in srcs:
                            try:
                                results[src.name] = await _run_source(db, client, src, ds_state, today, force, started)
                            except BlockedError as exc:
                                prev = (ds_state.get("sources") or {}).get(src.name, {})  # 保留上次的資料日期與已知的空白日
                                results[src.name] = {**prev, "ok": False, "rows": 0, "error": f"被擋：{exc}"[:300], "skipped": None, "at": started}
                                raise
                    finally:
                        if results:
                            await db[STATE_COLL].update_one({"_id": ds}, {"$set": _dataset_state(ds_state, results, started, len(srcs))}, upsert=True)
                            for n, r in results.items():
                                summary["sources"][n] = {k: v for k, v in r.items() if k != "empty_dates"}
                                summary["rows"] += r["rows"]
                                summary["errors"] += 1 if r["error"] else 0
            except BlockedError as exc:
                summary["aborted"] = "blocked"  # 被擋的那個來源已在上面的 results 計過一次錯誤
                summary["blocked_reason"] = str(exc)
                await db[STATE_COLL].update_one({"_id": META_ID}, {"$set": {"blocked_until": started + timedelta(hours=COOL_OFF_HOURS), "blocked_reason": str(exc), "blocked_at": started}}, upsert=True)
                logger.error("open_data: 被來源擋下，停止整輪並冷卻 %d 小時：%s", COOL_OFF_HOURS, exc)
            summary["requests"] = client.requests
            summary["finished_at"] = _utcnow()
            await db[RUNS_COLL].insert_one(dict(summary))
            old = await db[RUNS_COLL].find({}, {"_id": 1}).sort("started_at", -1).skip(RUNS_KEEP).to_list(length=None)
            if old:
                await db[RUNS_COLL].delete_many({"_id": {"$in": [o["_id"] for o in old]}})
            logger.info("open_data: %s 完成 datasets=%d rows=%d errors=%d requests=%d aborted=%s",
                        trigger, len(ds_list), summary["rows"], summary["errors"], summary["requests"], summary["aborted"])
            return summary
        finally:
            _running = False
            if own_client and client is not None:
                await client.aclose()


# ───────────────────────── 狀態與健康 ─────────────────────────

def evaluate_health(states: dict[str, dict], today: date, now: datetime) -> dict[str, Any]:
    """每個資料集的健康度。never＝還沒跑過；stale＝太久沒成功或資料日期落後；error＝只有失敗；partial＝有來源失敗。"""
    out: dict[str, Any] = {}
    for ds, spec in DATASETS.items():
        st = states.get(ds)
        row: dict[str, Any] = {"label": spec["label"], "status": "never", "last_success_at": None, "last_data_date": None, "last_error": None, "data_age_days": None}
        if st:
            row.update(last_success_at=st.get("last_success_at"), last_data_date=st.get("last_data_date"), last_error=st.get("last_error"))
            ok_at = st.get("last_success_at")
            dd = st.get("last_data_date")
            if dd and spec["data_days"] is not None:
                try:
                    row["data_age_days"] = (today - date.fromisoformat(str(dd)[:10])).days
                except ValueError:
                    pass
            if ok_at is None:
                row["status"] = "error" if st.get("last_error") else "never"
            elif (now - ok_at) > timedelta(days=spec["success_days"]):
                row["status"] = "stale"
            elif spec["data_days"] is not None and row["data_age_days"] is not None and row["data_age_days"] > spec["data_days"]:
                row["status"] = "stale"
            elif st.get("last_error"):
                row["status"] = "partial"
            else:
                row["status"] = "ok"
        out[ds] = row
    return out


def summarize_health(per_dataset: dict[str, Any], blocked_until: Optional[datetime], now: datetime) -> dict[str, Any]:
    bad = [k for k, v in per_dataset.items() if v["status"] in ("stale", "error")]
    partial = [k for k, v in per_dataset.items() if v["status"] == "partial"]
    cooling = bool(blocked_until and blocked_until > now)
    return {"ok": not bad and not cooling, "stale": bad, "partial": partial, "cooling_off": cooling, "datasets": per_dataset}


async def load_states(db) -> tuple[dict[str, dict], dict]:
    docs = await db[STATE_COLL].find({}).to_list(length=None)
    states = {d["_id"]: d for d in docs if d.get("_id") in DATASETS}
    meta = next((d for d in docs if d.get("_id") == META_ID), {})
    return states, meta


async def get_health(db=None) -> dict[str, Any]:
    db = db if db is not None else await _db()
    states, meta = await load_states(db)
    now = _utcnow()
    res = summarize_health(evaluate_health(states, tw_today(), now), meta.get("blocked_until"), now)
    res["running"] = _running
    return res


async def get_status(db=None) -> dict[str, Any]:
    db = db if db is not None else await _db()
    health = await get_health(db)
    counts = {ds: await db[spec["coll"]].estimated_document_count() for ds, spec in DATASETS.items()}
    states, meta = await load_states(db)
    runs = await db[RUNS_COLL].find({}, {"_id": 0}).sort("started_at", -1).limit(10).to_list(length=10)
    return {
        **health, "stored_counts": counts,
        "sources": {ds: (st.get("sources") or {}) for ds, st in states.items()},
        "blocked_until": meta.get("blocked_until"), "blocked_reason": meta.get("blocked_reason"),
        "recent_runs": runs,
    }


async def needs_catch_up(db=None, max_age_hours: float = 30.0, now: Optional[datetime] = None) -> bool:
    """有任何資料集從沒成功過、或超過 max_age_hours 沒成功——app 剛啟動時用來補跑（被擋冷卻中不算）。"""
    db = db if db is not None else await _db()
    states, meta = await load_states(db)
    now = now or _utcnow()
    if meta.get("blocked_until") and meta["blocked_until"] > now:
        return False
    for ds in DATASETS:
        at = (states.get(ds) or {}).get("last_success_at")
        if at is None or (now - at) > timedelta(hours=max_age_hours):
            return True
    return False
