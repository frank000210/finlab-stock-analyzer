"""事件研究台：事件日曆、事件簡報、價格反應、影片／文章論點抽取。

設計原則（跟待驗主張清冊同一個精神——流程可以幫你把功課做完整，但不預測漲跌）：

1. **事實、解讀、決策分三層**。簡報的每一則事實都要標來源分級（1 官方第一手／
   2 媒體／3 評論與社群）與「是否已證實」；影響地圖與情境是「解讀」，一律寫出
   機制與推翻條件；決策不存在伺服器，只存在使用者自己的瀏覽器。
2. **日期只收查得到出處的**。內建日曆每一筆都有官方來源網址與查證日期；依法規
   算出來的期限（月營收、季報）標明是規則推算。
3. **LLM 只做抽取，不做判斷**。論點抽取要求模型逐字引用原文，後端再核對引文
   是否真的出現在使用者貼上的文字裡（`quote_match`），對不上的會被標出來。
4. **價格反應是事後量測，不是訊號**。只算「事件前最後一個收盤 → 之後」的漲跌、
   相對大盤的差、量能倍數與均線位置。

這個模組不 import FastAPI；I/O（Mongo、FinMind、LLM）都由呼叫端注入或在函式內延後
import，純計算的部分可以直接單元測試。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CALENDAR_FILE = DATA_DIR / "event_calendar.json"
BRIEFS_DIR = DATA_DIR / "event_briefs"

BRIEFS_COLL = "ev_briefs"
CAL_COLL = "ev_calendar"

TW_TZ = timezone(timedelta(hours=8))

CATEGORIES: dict[str, str] = {
    "fed": "聯準會",
    "macro_us": "美國總經數據",
    "earnings": "財報／法說",
    "tw_statutory": "台股法定公告期限",
    "tw_market": "台股休市",
    "company": "公司事件",
    "policy": "政策／監管",
    "custom": "自訂",
}

MAX_CALENDAR_SPAN_DAYS = 400
MAX_REACTION_SYMBOLS = 20
REACTION_POST_DAYS = 10
CLAIMS_MIN_CHARS = 200
CLAIMS_MAX_CHARS = 20000
CLAIMS_MAX_ITEMS = 10

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL_RE = re.compile(r"^https?://[^\s]+$")


# ─────────────────────────── 小工具 ───────────────────────────

def tw_today() -> date:
    return datetime.now(TW_TZ).date()


def _check_iso(v: str) -> str:
    if not isinstance(v, str) or not _ISO_RE.match(v):
        raise ValueError("日期格式需為 YYYY-MM-DD")
    date.fromisoformat(v)  # 2026-02-30 這種會在這裡被擋
    return v


def _check_opt_iso(v: Optional[str]) -> Optional[str]:
    if v in (None, ""):
        return None
    return _check_iso(v)


def _check_url(v: str) -> str:
    """只收 http(s)。網址會被前端放進 href，這裡擋掉 javascript: 之類的 scheme。"""
    v = (v or "").strip()
    if v and not _URL_RE.match(v):
        raise ValueError("網址需以 http:// 或 https:// 開頭，且不能含空白")
    return v


def _domain(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


# ─────────────────────────── 資料模型 ───────────────────────────

class CalendarEvent(BaseModel):
    """內建或自訂的日曆事件。"""

    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9\-_.]*$")
    date: str
    end_date: Optional[str] = None
    title: str = Field(min_length=1, max_length=120)
    category: Literal["fed", "macro_us", "earnings", "tw_statutory", "tw_market", "company", "policy", "custom"]
    importance: int = Field(default=2, ge=1, le=3)
    time_note: str = Field(default="", max_length=200)
    source_name: str = Field(default="", max_length=80)
    source_url: str = Field(default="", max_length=500)
    verified_on: Optional[str] = None
    tentative: bool = False
    note: str = Field(default="", max_length=400)
    # 以美國時間發生的事件（數據、FOMC、美股盤後財報）都落在台股收盤之後，
    # 台股最快是「下一個交易日」才反應。
    us_time: bool = False

    _v_date = field_validator("date")(_check_iso)
    _v_end = field_validator("end_date", "verified_on")(_check_opt_iso)
    _v_url = field_validator("source_url")(_check_url)


class CustomEventIn(BaseModel):
    date: str
    title: str = Field(min_length=1, max_length=120)
    category: Literal["fed", "macro_us", "earnings", "company", "policy", "custom"] = "custom"
    importance: int = Field(default=2, ge=1, le=3)
    time_note: str = Field(default="", max_length=200)
    source_url: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=400)
    us_time: bool = False

    _v_date = field_validator("date")(_check_iso)
    _v_url = field_validator("source_url")(_check_url)


class Fact(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    # 1＝官方第一手（公告、財報、交易所資料）；2＝媒體報導；3＝評論、社群、影片
    tier: Literal[1, 2, 3]
    source_name: str = Field(min_length=1, max_length=80)
    source_url: str = Field(default="", max_length=500)
    date: Optional[str] = None
    # False＝「有人這樣報導／這樣說」，但沒有官方或當事人證實
    confirmed: bool = True

    _v_date = field_validator("date")(_check_opt_iso)
    _v_url = field_validator("source_url")(_check_url)


class Expectation(BaseModel):
    before: str = Field(default="", max_length=800)   # 事件前市場已經預期／反映了什麼
    actual: str = Field(default="", max_length=800)   # 實際發生什麼
    gap: str = Field(default="", max_length=800)      # 兩者的落差（市場反應的是這個）


class SymbolRef(BaseModel):
    symbol: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.\^\-]+$")
    name: str = Field(default="", max_length=40)


class ImpactNode(BaseModel):
    order: Literal[1, 2, 3]  # 1 直接；2 二階（供應鏈、客戶）；3 三階（資金面、評價、政策外溢）
    group: str = Field(min_length=1, max_length=60)
    symbols: list[SymbolRef] = Field(default_factory=list, max_length=12)
    direction: Literal["benefit", "hurt", "mixed", "unclear"]
    mechanism: str = Field(min_length=1, max_length=600)   # 為什麼會被影響（傳導機制）
    lag: str = Field(default="", max_length=120)           # 多久會反映在營收／訂單
    confidence: Literal["high", "medium", "low"] = "low"


class Scenario(BaseModel):
    key: Literal["base", "bull", "bear"]
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=800)
    triggers: list[str] = Field(default_factory=list, max_length=8)       # 看到什麼代表走向這個情境
    invalidation: list[str] = Field(default_factory=list, max_length=8)   # 看到什麼代表這個情境不成立
    watch: list[str] = Field(default_factory=list, max_length=8)          # 要盯的指標／日期

    @field_validator("triggers", "invalidation", "watch")
    @classmethod
    def _short_items(cls, v: list[str]) -> list[str]:
        out = [str(x).strip() for x in v if str(x).strip()]
        if any(len(x) > 300 for x in out):
            raise ValueError("每一條不能超過 300 字")
        return out


class KeyDate(BaseModel):
    date: str
    label: str = Field(min_length=1, max_length=120)
    source_url: str = Field(default="", max_length=500)
    tentative: bool = False
    us_time: bool = False

    _v_date = field_validator("date")(_check_iso)
    _v_url = field_validator("source_url")(_check_url)


class Viewpoint(BaseModel):
    """第三手觀點（分析師、YouTuber、法人評論）——只記假設與推翻條件，不記目標價。"""

    source: str = Field(min_length=1, max_length=80)
    stance: Literal["bullish", "bearish", "neutral", "unclear"] = "unclear"
    claim: str = Field(min_length=1, max_length=500)
    assumptions: str = Field(default="", max_length=500)
    source_url: str = Field(default="", max_length=500)

    _v_url = field_validator("source_url")(_check_url)


class EventBrief(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{2,63}$")
    title: str = Field(min_length=1, max_length=120)
    kind: Literal["scheduled", "shock"]            # 排定事件／突發事件
    status: Literal["developing", "closed"] = "developing"
    event_date: str                                 # 事件發生日（當地日期）
    tw_base_date: Optional[str] = None              # 台股「事件前最後一個交易日」；價格反應以這天收盤為基準
    episode_start: Optional[str] = None             # 醞釀期起點（事件前就開始發酵的那一天）
    as_of: str                                      # 這份簡報的資料截至哪一天
    summary: str = Field(min_length=1, max_length=1200)
    facts: list[Fact] = Field(min_length=1, max_length=40)
    expectation: Expectation = Field(default_factory=Expectation)
    impact: list[ImpactNode] = Field(default_factory=list, max_length=30)
    scenarios: list[Scenario] = Field(default_factory=list, max_length=3)
    key_dates: list[KeyDate] = Field(default_factory=list, max_length=20)
    open_questions: list[str] = Field(default_factory=list, max_length=12)
    viewpoints: list[Viewpoint] = Field(default_factory=list, max_length=12)

    _v_dates = field_validator("event_date", "as_of")(_check_iso)
    _v_opt = field_validator("tw_base_date", "episode_start")(_check_opt_iso)

    @field_validator("open_questions")
    @classmethod
    def _clean_questions(cls, v: list[str]) -> list[str]:
        out = [str(x).strip() for x in v if str(x).strip()]
        if any(len(x) > 300 for x in out):
            raise ValueError("每一條不能超過 300 字")
        return out

    @model_validator(mode="after")
    def _cross_checks(self) -> "EventBrief":
        keys = [s.key for s in self.scenarios]
        if len(keys) != len(set(keys)):
            raise ValueError("情境的 key（base／bull／bear）不能重複")
        if self.episode_start and self.tw_base_date and self.episode_start > self.tw_base_date:
            raise ValueError("episode_start（醞釀期起點）不能晚於 tw_base_date")
        if self.as_of < self.event_date and self.kind == "shock":
            raise ValueError("突發事件的 as_of（資料截至）不能早於 event_date")
        return self


def validate_brief(payload: Any) -> tuple[Optional[dict], list[str]]:
    """回傳 (通過驗證的 dict, 錯誤清單)。錯誤訊息是給人看的一行一條。"""
    try:
        brief = EventBrief.model_validate(payload)
    except ValidationError as exc:
        errors = []
        for e in exc.errors():
            loc = ".".join(str(x) for x in e.get("loc", ()))
            msg = str(e.get("msg", "")).replace("Value error, ", "")
            errors.append(f"{loc}：{msg}" if loc else msg)
        return None, errors
    return brief.model_dump(), []


# ─────────────────────────── 簡報完整度檢查 ───────────────────────────

def brief_quality(brief: dict) -> dict:
    """規則式的「功課有沒有做完」檢查——不評斷觀點對錯，只看流程有沒有漏步驟。"""
    facts = brief.get("facts") or []
    impact = brief.get("impact") or []
    scenarios = brief.get("scenarios") or []
    exp = brief.get("expectation") or {}

    tier1 = [f for f in facts if f.get("tier") == 1 and f.get("source_url")]
    domains = {d for d in (_domain(f.get("source_url", "")) for f in facts) if d}
    unsourced = [f for f in facts if f.get("tier") in (1, 2) and not f.get("source_url")]
    scen_keys = {s.get("key") for s in scenarios}
    weak_scen = [s for s in scenarios if not s.get("triggers") or not s.get("invalidation")]
    higher_order = [n for n in impact if n.get("order") in (2, 3)]

    items = [
        {
            "key": "tier1", "label": "至少一則官方第一手來源（附網址）", "ok": bool(tier1),
            "detail": f"{len(tier1)} 則" if tier1 else "目前全部是媒體或評論——先找到公告、財報或交易所資料",
        },
        {
            "key": "independent", "label": "事實來自至少 2 個獨立網域", "ok": len(domains) >= 2,
            "detail": f"{len(domains)} 個網域",
        },
        {
            "key": "sourced", "label": "官方與媒體來源的事實都附了網址", "ok": not unsourced,
            "detail": "全部有附" if not unsourced else f"{len(unsourced)} 則沒有網址",
        },
        {
            "key": "expectation", "label": "預期對照三格都有填（事前預期／實際／落差）",
            "ok": all(str(exp.get(k, "")).strip() for k in ("before", "actual", "gap")),
            "detail": "市場反應的是「落差」，不是事件本身的好壞",
        },
        {
            "key": "higher_order", "label": "影響地圖有二階或三階影響", "ok": bool(higher_order),
            "detail": f"直接 {len(impact) - len(higher_order)} 項、二三階 {len(higher_order)} 項",
        },
        {
            "key": "scenarios", "label": "基準／樂觀／悲觀三個情境齊全",
            "ok": scen_keys >= {"base", "bull", "bear"},
            "detail": f"已有 {len(scen_keys)} 個",
        },
        {
            "key": "invalidation", "label": "每個情境都有觸發條件與推翻條件",
            "ok": bool(scenarios) and not weak_scen,
            "detail": "全部有寫" if scenarios and not weak_scen else "沒寫推翻條件的情境，事後很容易硬凹",
        },
        {
            "key": "key_dates", "label": "列出後續關鍵日期", "ok": bool(brief.get("key_dates")),
            "detail": f"{len(brief.get('key_dates') or [])} 個",
        },
        {
            "key": "unknowns", "label": "寫下「還不知道的事」", "ok": bool(brief.get("open_questions")),
            "detail": f"{len(brief.get('open_questions') or [])} 條",
        },
    ]
    passed = sum(1 for i in items if i["ok"])
    unconfirmed = sum(1 for f in facts if not f.get("confirmed", True))
    return {
        "passed": passed, "total": len(items), "items": items,
        "fact_count": len(facts), "unconfirmed_count": unconfirmed,
        "tier_counts": {str(t): sum(1 for f in facts if f.get("tier") == t) for t in (1, 2, 3)},
    }


def brief_template() -> dict:
    """給編輯器用的空白模板。文字欄位裡的括號是填寫提示，存檔前要改掉。"""
    today = tw_today().isoformat()
    return {
        "id": "yyyy-mm-dd-short-name",
        "title": "（事件名稱，例如：某公司執行長異動）",
        "kind": "shock",
        "status": "developing",
        "event_date": today,
        "tw_base_date": None,
        "episode_start": None,
        "as_of": today,
        "summary": "（三句話：發生什麼、為什麼重要、目前最大的未知數）",
        "facts": [
            {"text": "（一則可查證的事實）", "tier": 1, "source_name": "（公司公告／交易所／財報）",
             "source_url": "", "date": today, "confirmed": True},
        ],
        "expectation": {
            "before": "（事件前市場已經預期或反映了什麼：共識數字、事前股價已漲跌多少）",
            "actual": "（實際發生什麼）",
            "gap": "（落差在哪裡——市場反應的是這個）",
        },
        "impact": [
            {"order": 1, "group": "（直接影響的對象）", "symbols": [{"symbol": "2330", "name": "台積電"}],
             "direction": "unclear", "mechanism": "（為什麼會被影響）", "lag": "（多久反映在營收）",
             "confidence": "low"},
        ],
        "scenarios": [
            {"key": "base", "title": "基準", "description": "（最可能的發展）",
             "triggers": ["（看到什麼代表走這條路）"], "invalidation": ["（看到什麼代表不成立）"], "watch": []},
            {"key": "bull", "title": "樂觀", "description": "", "triggers": [], "invalidation": [], "watch": []},
            {"key": "bear", "title": "悲觀", "description": "", "triggers": [], "invalidation": [], "watch": []},
        ],
        "key_dates": [{"date": today, "label": "（後續關鍵日期）", "source_url": "", "tentative": False, "us_time": False}],
        "open_questions": ["（還不知道、但會改變判斷的事）"],
        "viewpoints": [],
    }


# ─────────────────────────── 內建資料載入 ───────────────────────────

@lru_cache(maxsize=1)
def _calendar_file() -> dict:
    try:
        return json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        logger.exception("event_calendar.json 讀取失敗")
        return {"events": [], "tw_market_closed": {"days": []}}


@lru_cache(maxsize=1)
def load_builtin_events() -> tuple[dict, ...]:
    out = []
    for raw in _calendar_file().get("events", []):
        try:
            out.append(CalendarEvent.model_validate(raw).model_dump())
        except ValidationError as exc:
            logger.error("內建日曆事件格式錯誤，略過：%s（%s）", raw.get("id"), exc.errors()[:1])
    return tuple(out)


@lru_cache(maxsize=1)
def tw_closed_days() -> dict[str, str]:
    """{日期: 名稱}，含週末那幾天（照交易所公告原樣存），判斷時再排除週末。"""
    days = (_calendar_file().get("tw_market_closed") or {}).get("days", [])
    return {d["date"]: d.get("name", "休市") for d in days if _ISO_RE.match(str(d.get("date", "")))}


def calendar_meta() -> dict:
    f = _calendar_file()
    closed = f.get("tw_market_closed") or {}
    return {
        "verified_on": f.get("verified_on"),
        "holiday_source_name": closed.get("source_name", ""),
        "holiday_source_url": closed.get("source_url", ""),
        "holiday_covers": closed.get("covers", []),
        "categories": CATEGORIES,
    }


@lru_cache(maxsize=1)
def load_builtin_briefs() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not BRIEFS_DIR.is_dir():
        return out
    for path in sorted(BRIEFS_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            logger.exception("內建簡報讀取失敗：%s", path.name)
            continue
        brief, errors = validate_brief(raw)
        if brief is None:
            logger.error("內建簡報格式錯誤，略過：%s（%s）", path.name, "; ".join(errors[:3]))
            continue
        brief["builtin"] = True
        out[brief["id"]] = brief
    return out


def clear_builtin_cache() -> None:
    for fn in (_calendar_file, load_builtin_events, tw_closed_days, load_builtin_briefs):
        fn.cache_clear()


# ─────────────────────────── 交易日與規則式事件 ───────────────────────────

def is_tw_trading_day(d: date, closed: Optional[dict[str, str]] = None) -> bool:
    closed = tw_closed_days() if closed is None else closed
    return d.weekday() < 5 and d.isoformat() not in closed


def next_tw_trading_day(d: date, closed: Optional[dict[str, str]] = None, inclusive: bool = False) -> date:
    """d 之後（inclusive=True 時含 d）的第一個台股交易日。只認得已載入的休市日。"""
    cur = d if inclusive else d + timedelta(days=1)
    for _ in range(40):
        if is_tw_trading_day(cur, closed):
            return cur
        cur += timedelta(days=1)
    return cur


def holiday_events(start: date, end: date, closed: Optional[dict[str, str]] = None) -> list[dict]:
    """把交易所公告的休市日併成一段一段（含夾在中間的週末），只留有平日休市的區段。"""
    closed = tw_closed_days() if closed is None else closed
    meta = calendar_meta()
    out: list[dict] = []
    days = sorted(d for d in closed if (start - timedelta(days=14)).isoformat() <= d <= (end + timedelta(days=14)).isoformat())
    weekday_closed = [date.fromisoformat(d) for d in days if date.fromisoformat(d).weekday() < 5]
    seen: set[date] = set()
    for d in weekday_closed:
        if d in seen:
            continue
        lo = d
        while not is_tw_trading_day(lo - timedelta(days=1), closed):
            lo -= timedelta(days=1)
            if (d - lo).days > 20:
                break
        hi = d
        while not is_tw_trading_day(hi + timedelta(days=1), closed):
            hi += timedelta(days=1)
            if (hi - d).days > 20:
                break
        block = [lo + timedelta(days=i) for i in range((hi - lo).days + 1)]
        seen.update(block)
        # 區段的頭尾若是週末就修掉，顯示「實際少掉的交易日」範圍
        first = next(x for x in block if x.weekday() < 5 and x.isoformat() in closed)
        last = next(x for x in reversed(block) if x.weekday() < 5 and x.isoformat() in closed)
        if last < start or first > end:
            continue
        # 一段連假可能有好幾個名目（結算交割日＋春節），標題用佔最多平日的那個
        counts: dict[str, int] = {}
        for x in block:
            n = closed.get(x.isoformat())
            if n and x.weekday() < 5:
                counts[n] = counts.get(n, 0) + 1
        main_name = max(counts, key=lambda k: counts[k]) if counts else "休市"
        resume = next_tw_trading_day(last, closed)
        lost = sum(1 for x in block if x.weekday() < 5)
        title = f"台股休市：{main_name}"
        out.append({
            "id": f"twclosed-{first.isoformat()}",
            "date": first.isoformat(),
            "end_date": last.isoformat() if last != first else None,
            "title": title[:120],
            "category": "tw_market",
            "importance": 2 if lost >= 2 else 1,
            "time_note": f"少 {lost} 個交易日，{resume.month}/{resume.day} 恢復交易",
            "source_name": meta["holiday_source_name"],
            "source_url": meta["holiday_source_url"],
            "verified_on": meta["verified_on"],
            "tentative": False,
            "note": "休市期間美股照常交易，消息會累積到恢復交易那天一次反應。",
            "us_time": False,
            "origin": "rule",
        })
    return out


_LAW_URL = "https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode=G0400001&flno=36"
# (月, 日, 標題)：證券交易法第 36 條——年報為會計年度終了後三個月內，
# 第一、二、三季為每季終了後 45 日內。
_FIN_DEADLINES = [
    (3, 31, "年度財報公告期限（上一年度）"),
    (5, 15, "第 1 季財報公告期限"),
    (8, 14, "第 2 季財報公告期限"),
    (11, 14, "第 3 季財報公告期限"),
]


def statutory_events(start: date, end: date, closed: Optional[dict[str, str]] = None) -> list[dict]:
    """依法規推算的公告期限：每月 10 日前公告上月營收、季報／年報期限。遇假日順延。"""
    closed = tw_closed_days() if closed is None else closed
    out: list[dict] = []

    def _roll(d: date) -> tuple[date, bool]:
        rolled = next_tw_trading_day(d, closed, inclusive=True)
        return rolled, rolled != d

    y, m = start.year, start.month
    # 往前多看一個月，順延後落在範圍內的也要算進來
    m -= 1
    if m == 0:
        y, m = y - 1, 12
    while date(y, m, 1) <= end:
        due, rolled = _roll(date(y, m, 10))
        prev_m = 12 if m == 1 else m - 1
        if start <= due <= end:
            out.append({
                "id": f"twrev-{y}-{m:02d}",
                "date": due.isoformat(), "end_date": None,
                "title": f"上市櫃公司 {prev_m} 月營收公告期限",
                "category": "tw_statutory", "importance": 2,
                "time_note": "法定 10 日前" + ("，遇假日順延" if rolled else "") + "；多數公司集中在最後兩三天公告",
                "source_name": "證券交易法第 36 條", "source_url": _LAW_URL,
                "verified_on": None, "tentative": False,
                "note": "規則推算的期限，不是個別公司的實際公告日。",
                "us_time": False, "origin": "rule",
            })
        m += 1
        if m == 13:
            y, m = y + 1, 1

    for year in range(start.year - 1, end.year + 1):
        for month, day, label in _FIN_DEADLINES:
            due, rolled = _roll(date(year, month, day))
            if start <= due <= end:
                out.append({
                    "id": f"twfin-{year}-{month:02d}",
                    "date": due.isoformat(), "end_date": None,
                    "title": f"上市櫃公司{label}",
                    "category": "tw_statutory", "importance": 2,
                    "time_note": f"法定 {month}/{day}" + ("，遇假日順延" if rolled else "") + "；金融業另有規定",
                    "source_name": "證券交易法第 36 條", "source_url": _LAW_URL,
                    "verified_on": None, "tentative": False,
                    "note": "規則推算的期限。大型公司通常提早公告並召開法說會。",
                    "us_time": False, "origin": "rule",
                })
    return out


def brief_key_date_events(briefs: list[dict]) -> list[dict]:
    out = []
    for b in briefs:
        for i, kd in enumerate(b.get("key_dates") or []):
            out.append({
                "id": f"brief-{b['id']}-{i}",
                "date": kd["date"], "end_date": None,
                "title": kd["label"],
                "category": "company", "importance": 3,
                "time_note": "", "source_name": "", "source_url": kd.get("source_url", ""),
                "verified_on": None, "tentative": bool(kd.get("tentative")),
                "note": f"來自事件簡報：{b.get('title', '')}",
                "us_time": bool(kd.get("us_time")),
                "origin": "brief", "brief_id": b["id"], "brief_title": b.get("title", ""),
            })
    return out


def build_calendar(
    start: date,
    end: date,
    custom: Optional[list[dict]] = None,
    briefs: Optional[list[dict]] = None,
    today: Optional[date] = None,
    closed: Optional[dict[str, str]] = None,
) -> list[dict]:
    """合併內建、規則推算、簡報關鍵日期與自訂事件，回傳範圍內依日期排序的清單。"""
    if end < start:
        start, end = end, start
    if (end - start).days > MAX_CALENDAR_SPAN_DAYS:
        end = start + timedelta(days=MAX_CALENDAR_SPAN_DAYS)
    today = today or tw_today()
    closed = tw_closed_days() if closed is None else closed

    events: list[dict] = [{**e, "origin": "builtin"} for e in load_builtin_events()]
    events += holiday_events(start, end, closed)
    events += statutory_events(start, end, closed)
    events += [{**e, "origin": "custom"} for e in (custom or [])]

    # 簡報的關鍵日期若跟既有事件是同一件事（同一天、同一個來源網址），就把簡報連結
    # 掛到既有事件上，不重複列兩筆。
    index = {(e["date"], e.get("source_url")): e for e in events if e.get("source_url")}
    for be in brief_key_date_events(briefs or []):
        hit = index.get((be["date"], be.get("source_url"))) if be.get("source_url") else None
        if hit is not None:
            hit.setdefault("brief_id", be["brief_id"])
            hit.setdefault("brief_title", be["brief_title"])
        else:
            events.append(be)

    out, seen = [], set()
    s_iso, e_iso = start.isoformat(), end.isoformat()
    for e in events:
        last = e.get("end_date") or e["date"]
        if last < s_iso or e["date"] > e_iso or e["id"] in seen:
            continue
        seen.add(e["id"])
        d = date.fromisoformat(e["date"])
        row = dict(e)
        row["category_label"] = CATEGORIES.get(row["category"], row["category"])
        row["days_away"] = (d - today).days
        row["weekday"] = "一二三四五六日"[d.weekday()]
        if row.get("us_time"):
            row["tw_reaction_date"] = next_tw_trading_day(d, closed).isoformat()
        elif row["category"] not in ("tw_market",) and not is_tw_trading_day(d, closed):
            row["tw_reaction_date"] = next_tw_trading_day(d, closed).isoformat()
        else:
            row["tw_reaction_date"] = None
        out.append(row)
    out.sort(key=lambda r: (r["date"], -int(r.get("importance", 2)), r["title"]))
    return out


def custom_event_doc(payload: CustomEventIn) -> dict:
    digest = hashlib.sha1(f"{payload.date}|{payload.title}".encode("utf-8")).hexdigest()[:10]
    doc = payload.model_dump()
    doc.update({"id": f"c-{digest}", "end_date": None, "source_name": "", "verified_on": None, "tentative": False})
    return doc


# ─────────────────────────── 簡報儲存（Mongo＋內建檔） ───────────────────────────

def _strip_mongo(doc: dict) -> dict:
    d = {k: v for k, v in doc.items() if k != "_id"}
    d["builtin"] = False
    return d


async def list_briefs(db=None) -> list[dict]:
    """內建＋使用者建立的簡報，事件日期新的在前。Mongo 壞掉時只回內建的。"""
    briefs = dict(load_builtin_briefs())
    if db is not None:
        try:
            async for doc in db[BRIEFS_COLL].find({}):
                b = _strip_mongo(doc)
                if b.get("id") and b["id"] not in briefs:
                    briefs[b["id"]] = b
        except Exception:  # noqa: BLE001
            logger.exception("讀取 ev_briefs 失敗，只回內建簡報")
    return sorted(briefs.values(), key=lambda b: (b.get("event_date", ""), b.get("id", "")), reverse=True)


async def get_brief(brief_id: str, db=None) -> Optional[dict]:
    builtin = load_builtin_briefs().get(brief_id)
    if builtin is not None:
        return builtin
    if db is None:
        return None
    try:
        doc = await db[BRIEFS_COLL].find_one({"_id": brief_id})
    except Exception:  # noqa: BLE001
        logger.exception("讀取 ev_briefs 失敗")
        return None
    return _strip_mongo(doc) if doc else None


async def save_brief(brief: dict, db, now: Optional[datetime] = None) -> dict:
    if brief["id"] in load_builtin_briefs():
        raise PermissionError("這個 id 是內建簡報（隨程式版本發布），不能覆寫；請換一個 id。")
    now = now or datetime.now(timezone.utc)
    doc = {k: v for k, v in brief.items() if k != "builtin"}
    doc["updated_at"] = now.isoformat()
    await db[BRIEFS_COLL].update_one({"_id": doc["id"]}, {"$set": doc}, upsert=True)
    return {**doc, "builtin": False}


async def delete_brief(brief_id: str, db) -> bool:
    if brief_id in load_builtin_briefs():
        raise PermissionError("內建簡報不能刪除。")
    res = await db[BRIEFS_COLL].delete_one({"_id": brief_id})
    return bool(getattr(res, "deleted_count", 0))


def brief_summary(b: dict) -> dict:
    q = brief_quality(b)
    return {
        "id": b["id"], "title": b["title"], "kind": b["kind"], "status": b.get("status", "developing"),
        "event_date": b["event_date"], "as_of": b["as_of"], "summary": b["summary"],
        "builtin": bool(b.get("builtin")), "quality_passed": q["passed"], "quality_total": q["total"],
        "fact_count": q["fact_count"], "unconfirmed_count": q["unconfirmed_count"],
        "next_key_date": next((k["date"] for k in sorted(b.get("key_dates") or [], key=lambda k: k["date"])
                               if k["date"] >= tw_today().isoformat()), None),
    }


# ─────────────────────────── 價格反應 ───────────────────────────

def _pct(a: float, b: float) -> Optional[float]:
    if not b:
        return None
    return round((a / b - 1.0) * 100.0, 2)


def _last_idx_on_or_before(rows: list[dict], iso: str) -> Optional[int]:
    idx = None
    for i, r in enumerate(rows):
        if r["date"] <= iso:
            idx = i
        else:
            break
    return idx


def _sma(closes: list[float], n: int) -> Optional[float]:
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 2)


def reaction_row(rows: list[dict], base_date: str, episode_start: Optional[str] = None) -> dict:
    """單一標的的事件反應。rows 需依日期遞增，每筆 {date, close, volume}。"""
    rows = [r for r in rows if r.get("close")]
    bi = _last_idx_on_or_before(rows, base_date)
    if bi is None:
        return {"error": "沒有事件前的價格資料"}
    base = rows[bi]
    post = rows[bi + 1: bi + 1 + REACTION_POST_DAYS]
    out: dict[str, Any] = {
        "base_date": base["date"], "base_close": base["close"],
        "days_since": len(rows) - 1 - bi,
        "day1_date": None, "day1_pct": None, "latest_date": None, "latest_close": None, "latest_pct": None,
        "pre_pct": None, "pre_low_pct": None, "pre_low_date": None, "episode_from": None,
        "vol_ratio_day1": None, "ma20": None, "ma60": None, "above_ma20": None, "above_ma60": None,
        "path": [{"date": r["date"], "pct": _pct(r["close"], base["close"])} for r in post],
    }
    if post:
        out["day1_date"] = post[0]["date"]
        out["day1_pct"] = _pct(post[0]["close"], base["close"])
        vols = [r.get("volume") or 0 for r in rows[max(0, bi - 19): bi + 1]]
        avg = sum(vols) / len(vols) if vols else 0
        if avg > 0 and post[0].get("volume"):
            out["vol_ratio_day1"] = round(post[0]["volume"] / avg, 2)
    if len(rows) - 1 > bi:
        latest = rows[-1]
        out["latest_date"] = latest["date"]
        out["latest_close"] = latest["close"]
        out["latest_pct"] = _pct(latest["close"], base["close"])
    if episode_start and episode_start < base["date"]:
        ei = _last_idx_on_or_before(rows, episode_start)
        if ei is not None and ei < bi:
            ep = rows[ei]
            out["episode_from"] = ep["date"]
            out["pre_pct"] = _pct(base["close"], ep["close"])
            window = rows[ei: bi + 1]
            low = min(window, key=lambda r: r["close"])
            out["pre_low_pct"] = _pct(low["close"], ep["close"])
            out["pre_low_date"] = low["date"]
    closes = [r["close"] for r in rows]
    last_close = closes[-1]
    out["ma20"], out["ma60"] = _sma(closes, 20), _sma(closes, 60)
    out["above_ma20"] = None if out["ma20"] is None else last_close >= out["ma20"]
    out["above_ma60"] = None if out["ma60"] is None else last_close >= out["ma60"]
    return out


def compute_reaction(
    prices: dict[str, list[dict]],
    bench: list[dict],
    base_date: str,
    episode_start: Optional[str] = None,
    meta: Optional[dict[str, dict]] = None,
) -> dict:
    """prices: {代號: rows}；bench: 大盤 rows。回傳各標的反應與相對大盤的差。"""
    meta = meta or {}
    b = reaction_row(bench, base_date, episode_start) if bench else {"error": "沒有大盤資料"}
    rows = []
    for sym, series in prices.items():
        r = reaction_row(series, base_date, episode_start) if series else {"error": "沒有價格資料"}
        r["symbol"] = sym
        r.update(meta.get(sym, {}))
        for key in ("day1", "latest", "pre"):
            pct, bpct = r.get(f"{key}_pct"), b.get(f"{key}_pct")
            date_key = {"day1": "day1_date", "latest": "latest_date", "pre": "episode_from"}[key]
            same_day = r.get(date_key) is not None and r.get(date_key) == b.get(date_key)
            r[f"{key}_excess"] = round(pct - bpct, 2) if (pct is not None and bpct is not None and same_day) else None
        rows.append(r)
    return {"base_date": base_date, "episode_start": episode_start, "bench": b, "rows": rows}


def reaction_targets(brief: dict) -> tuple[list[str], dict[str, dict]]:
    """從影響地圖挑出台股代號（去重、保留順序、有上限），以及每檔的名稱／方向／階數。"""
    from ..data.us_symbols import is_tw_symbol, normalize_symbol

    symbols: list[str] = []
    meta: dict[str, dict] = {}
    for node in brief.get("impact") or []:
        for ref in node.get("symbols") or []:
            sym = normalize_symbol(str(ref.get("symbol", "")))
            if not sym or not is_tw_symbol(sym) or sym in meta:
                continue
            if len(symbols) >= MAX_REACTION_SYMBOLS:
                break
            symbols.append(sym)
            meta[sym] = {"name": ref.get("name", ""), "group": node.get("group", ""),
                         "order": node.get("order"), "direction": node.get("direction")}
    return symbols, meta


PriceFetcher = Callable[[str, str, str], Awaitable[list[dict]]]


async def _finmind_prices(symbol: str, start: str, end: str) -> list[dict]:
    from ..crawler.finmind_client import FinMindClient

    df = await FinMindClient().get_stock_price(symbol, start, end)
    if df is None or df.empty:
        return []
    rows = []
    for _, r in df.sort_values("date").iterrows():
        try:
            close = float(r["close"])
        except (TypeError, ValueError):
            continue
        if close <= 0:
            continue
        try:
            vol = float(r.get("volume") or 0)
        except (TypeError, ValueError):
            vol = 0.0
        rows.append({"date": str(r["date"])[:10], "close": close, "volume": vol})
    return rows


async def fetch_reaction(brief: dict, fetch: Optional[PriceFetcher] = None, today: Optional[date] = None) -> dict:
    """抓影響地圖裡台股標的與大盤的日線，算事件反應。每檔 1 次 FinMind 呼叫。"""
    base_date = brief.get("tw_base_date")
    if not base_date:
        raise ValueError("這份簡報沒有設定 tw_base_date（台股事件前最後一個交易日），無法計算價格反應。")
    symbols, meta = reaction_targets(brief)
    if not symbols:
        raise ValueError("影響地圖裡沒有台股代號，無法計算價格反應。")
    fetch = fetch or _finmind_prices
    today = today or tw_today()
    episode_start = brief.get("episode_start")
    anchor = date.fromisoformat(episode_start or base_date)
    start = (anchor - timedelta(days=150)).isoformat()  # 留夠算 60 日均線的長度
    end = today.isoformat()

    sem = asyncio.Semaphore(3)
    errors: dict[str, str] = {}

    async def _one(sym: str) -> list[dict]:
        async with sem:
            try:
                return await fetch(sym, start, end)
            except Exception as exc:  # noqa: BLE001
                logger.warning("event reaction: %s 價格取得失敗：%s", sym, exc)
                errors[sym] = "價格取得失敗"
                return []

    series = await asyncio.gather(*[_one(s) for s in symbols], _one("TAIEX"))
    bench = series[-1]
    prices = dict(zip(symbols, series[:-1]))
    result = compute_reaction(prices, bench, base_date, episode_start, meta)
    result.update({
        "brief_id": brief["id"], "as_of": end, "errors": errors,
        "complete": not errors and bool(bench) and all(prices.values()),
        "note": "事後量測，不是訊號：漲跌以事件前最後一個收盤為基準；超額＝個股漲跌減大盤漲跌。",
    })
    return result


# ─────────────────────────── 論點抽取（LLM） ───────────────────────────

CLAIMS_SYSTEM_PROMPT = """你是投資研究助理，負責把一段財經影片逐字稿或文章，拆成「可以被檢驗的論點」。

嚴格規則：
1. 只能使用使用者貼上的文字。不得補充文字裡沒有的事實、數字或你自己的判斷。
2. 每個論點都要附 quote：從原文「逐字照抄」一段 15～60 字的原句（不要改寫、不要
   翻譯、不要繁簡轉換、不要加刪標點以外的字）。找不到可以照抄的原句，就不要列這個論點。
3. kind 三選一：fact（講者當成事實陳述、原則上可查證）、forecast（對未來的預測）、
   opinion（評價或建議）。
4. assumptions：這個論點要成立，講者依賴了哪些前提（講者明講或明顯隱含的才寫）。
5. invalidation：講者有沒有說「什麼情況下他會改變看法」。有就寫，沒有就填空字串，
   不要替他補。
6. checkable：這個論點事後能不能用公開資料驗證；check_how 寫要看什麼資料、什麼時候看。
7. 不提供投資建議，不評論講者對錯，不給目標價。
8. 最多列 8 個最重要的論點。

只輸出一個 JSON 物件，不要有任何其他文字或 markdown 圍欄。格式：
{"stance":"偏多|偏空|中性|不明",
 "claims":[{"quote":"","claim":"","kind":"fact|forecast|opinion","assumptions":[""],
            "invalidation":"","horizon":"","checkable":true,"check_how":""}],
 "missing":["講者沒有交代、但判斷這段內容時需要知道的事"]}

claim、assumptions、invalidation、horizon、check_how、missing 用臺灣用語的繁體中文；
quote 維持原文原樣。"""


def parse_llm_json(text: str) -> dict:
    """LLM 常把 JSON 包在 ```json 圍欄或前後加說明文字；取第一個 { 到最後一個 }。"""
    s = (text or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    lo, hi = s.find("{"), s.rfind("}")
    if lo < 0 or hi <= lo:
        raise ValueError("AI 回應不是 JSON")
    obj = json.loads(s[lo: hi + 1])
    if not isinstance(obj, dict):
        raise ValueError("AI 回應不是 JSON 物件")
    return obj


_KEEP_RE = re.compile(r"[^0-9A-Za-z一-鿿㐀-䶿]+")


def normalize_for_match(s: str) -> str:
    """比對引文用：去掉空白與標點、英文轉小寫。語音轉文字的斷句和標點很亂，不該影響比對。"""
    return _KEEP_RE.sub("", s or "").lower()


def quote_match(quote: str, norm_text: str) -> str:
    """exact＝原文裡找得到整句；approx＝大部分片段找得到（多半是斷句差異）；none＝找不到。"""
    q = normalize_for_match(quote)
    if len(q) < 6:
        return "none"
    if q in norm_text:
        return "exact"
    n = 5
    grams = [q[i: i + n] for i in range(len(q) - n + 1)]
    hit = sum(1 for g in grams if g in norm_text)
    return "approx" if grams and hit / len(grams) >= 0.7 else "none"


_KINDS = {"fact": "fact", "forecast": "forecast", "opinion": "opinion",
          "事實": "fact", "預測": "forecast", "意見": "opinion", "觀點": "opinion"}
_STANCES = {"偏多", "偏空", "中性", "不明"}


def _clip(v: Any, n: int) -> str:
    return str(v or "").strip()[:n]


def postprocess_claims(raw: dict, text: str) -> dict:
    """把 LLM 輸出整理成固定格式，並核對每一句引文是否真的出現在原文。"""
    norm_text = normalize_for_match(text)
    claims = []
    for item in (raw.get("claims") or [])[:CLAIMS_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        claim = _clip(item.get("claim"), 300)
        quote = _clip(item.get("quote"), 200)
        if not claim:
            continue
        assumptions = item.get("assumptions") or []
        if isinstance(assumptions, str):
            assumptions = [assumptions]
        claims.append({
            "claim": claim,
            "quote": quote,
            "quote_match": quote_match(quote, norm_text) if quote else "none",
            "kind": _KINDS.get(str(item.get("kind", "")).strip().lower(), "opinion"),
            "assumptions": [_clip(a, 200) for a in assumptions if _clip(a, 200)][:5],
            "invalidation": _clip(item.get("invalidation"), 300),
            "horizon": _clip(item.get("horizon"), 80),
            "checkable": bool(item.get("checkable")),
            "check_how": _clip(item.get("check_how"), 300),
        })
    stance = _clip(raw.get("stance"), 10)
    missing = raw.get("missing") or []
    if isinstance(missing, str):
        missing = [missing]
    verified = sum(1 for c in claims if c["quote_match"] != "none")
    return {
        "stance": stance if stance in _STANCES else "不明",
        "claims": claims,
        "missing": [_clip(m, 200) for m in missing if _clip(m, 200)][:6],
        "stats": {
            "total": len(claims),
            "quote_verified": verified,
            "quote_unverified": len(claims) - verified,
            "with_invalidation": sum(1 for c in claims if c["invalidation"]),
            "forecasts": sum(1 for c in claims if c["kind"] == "forecast"),
            "checkable": sum(1 for c in claims if c["checkable"]),
        },
    }


def check_claims_input(text: str) -> str:
    text = (text or "").strip()
    if len(text) < CLAIMS_MIN_CHARS:
        raise ValueError(f"內容太短（至少 {CLAIMS_MIN_CHARS} 字），抽不出有意義的論點。")
    if len(text) > CLAIMS_MAX_CHARS:
        raise ValueError(f"內容超過 {CLAIMS_MAX_CHARS} 字，請分段貼上（一段影片約 20 分鐘為宜）。")
    return text


async def extract_claims(text: str, source: str = "", llm=None) -> dict:
    """抽出論點並核對引文。llm 可注入（測試用）；預設用全站共用的 llm_complete。"""
    text = check_claims_input(text)
    source = _clip(source, 80)
    if llm is None:
        from ..llm import llm_complete as llm

    key = "event_claims:v1:" + hashlib.sha1(text.encode("utf-8")).hexdigest()
    try:
        from ..db.cache import get_cache, set_cache
    except Exception:  # noqa: BLE001
        get_cache = set_cache = None
    if get_cache is not None:
        try:
            cached = await get_cache(key)
            if cached:
                return {**cached, "source": source, "cached": True}
        except Exception:  # noqa: BLE001
            pass

    user = (f"來源：{source}\n\n" if source else "") + "以下是要拆解的文字：\n\n" + text
    answer = await llm(CLAIMS_SYSTEM_PROMPT, user, max_tokens=3000, temperature=0.1)
    result = postprocess_claims(parse_llm_json(answer), text)
    result.update({"chars": len(text), "as_of": tw_today().isoformat()})
    if set_cache is not None and result["claims"]:
        try:
            await set_cache(key, result, "ai_summary")
        except Exception:  # noqa: BLE001
            pass
    return {**result, "source": source, "cached": False}
