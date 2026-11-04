"""ETF 配息「來源」資料：驗證、載入、匯入合併（純檔案處理，不碰網路與資料庫）。

為什麼不是爬蟲：配息來源（本期淨投資收益／已實現資本利得／收益平準金／本金）只寫在各投信
的收益分配公告裡。調查結果（2026-11）：各家格式不一、多為動態載入頁面；國泰與證交所的網站
對非瀏覽器存取直接回拒絕，不應硬繞；FinMind 免費版沒有這類資料集；MoneyDJ 的 robots.txt
明文禁止資料探勘。所以這裡只做兩件事——
1. 讓「人工對照公告後整理出來的資料」有嚴格驗證的落腳處（backend/app/data/etf_distribution_sources.json，
   每筆必須附來源名稱、https 連結與公告日，缺一筆都不收），由 scripts/etf_distribution_import.py 匯入；
2. 頁面另外提供「自己填」的路徑（存在使用者的瀏覽器，見前端 distributionSource.js）。
絕不放沒有出處的數字。

單位一律是「每受益權單位的配息金額（元）」，四個組成：
  income 本期淨投資收益（成分股股利、利息）、gain 已實現資本利得、equalization 收益平準金、principal 本金（其他）。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "etf_distribution_sources.json"
PARTS = ("income", "gain", "equalization", "principal")
SCHEMA_VERSION = 1
_SYMBOL_RE = re.compile(r"^[0-9A-Z]{3,8}$")


def _is_day(s) -> bool:
    try:
        date.fromisoformat(str(s))
        return len(str(s)) == 10
    except ValueError:
        return False


def validate_entry(e: dict) -> list[str]:
    """回傳錯誤清單；空清單代表這筆可以收。"""
    errs: list[str] = []
    if not isinstance(e, dict):
        return ["不是物件"]
    if not _SYMBOL_RE.match(str(e.get("symbol", ""))):
        errs.append("symbol 格式不對")
    if not _is_day(e.get("ex_date")):
        errs.append("ex_date 需為 YYYY-MM-DD")
    if not _is_day(e.get("as_of")):
        errs.append("as_of（公告日）需為 YYYY-MM-DD")
    if not str(e.get("source", "")).strip():
        errs.append("缺 source（來源名稱，例如「○○投信 收益分配公告」）")
    if not str(e.get("source_url", "")).startswith("https://"):
        errs.append("source_url 必須是 https:// 開頭的公告連結")
    pu = e.get("per_unit")
    if not isinstance(pu, dict) or set(pu) != set(PARTS):
        errs.append(f"per_unit 必須剛好有 {', '.join(PARTS)} 四個欄位")
    else:
        vals = []
        for k in PARTS:
            v = pu[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                errs.append(f"per_unit.{k} 需為 ≥ 0 的數字")
            else:
                vals.append(float(v))
        if len(vals) == len(PARTS) and sum(vals) <= 0:
            errs.append("per_unit 四項合計需 > 0")
    return errs


def _key(e: dict) -> tuple[str, str]:
    return str(e["symbol"]).upper(), str(e["ex_date"])


def merge_entries(existing: list[dict], new: list[dict]) -> tuple[list[dict], dict]:
    """把 new 併進 existing（同 symbol＋ex_date 以新的取代），驗證不過的略過並回報。"""
    by_key: dict[tuple[str, str], dict] = {}
    for e in existing:
        if not validate_entry(e):
            by_key[_key(e)] = e
    report = {"added": 0, "replaced": 0, "rejected": []}
    for i, e in enumerate(new):
        if isinstance(e, dict) and "symbol" in e:
            e = {**e, "symbol": str(e["symbol"]).strip().upper()}  # 代碼大小寫不同不算錯，先正規化再驗證
        errs = validate_entry(e)
        if errs:
            report["rejected"].append({"index": i, "symbol": e.get("symbol") if isinstance(e, dict) else None, "errors": errs})
            continue
        report["replaced" if _key(e) in by_key else "added"] += 1
        by_key[_key(e)] = e
    merged = sorted(by_key.values(), key=lambda x: (x["symbol"], x["ex_date"]))
    return merged, report


def dump_document(entries: list[dict]) -> str:
    doc = {
        "schema_version": SCHEMA_VERSION,
        "_note": "每筆 per_unit 單位＝元／受益權單位。只收有出處的人工整理資料，由 scripts/etf_distribution_import.py 匯入；不要手改後不驗證。",
        "entries": entries,
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


_cache: dict = {"mtime": None, "path": None, "data": {}}


def load_entries(path: Optional[Path] = None) -> dict[str, list[dict]]:
    """symbol → 依除息日排序的來源資料。檔案不存在、壞掉都回空（頁面顯示「尚未收錄」，不報錯）。
    以檔案修改時間快取，改檔後不必重啟。"""
    p = Path(path) if path else DATA_PATH
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return {}
    if _cache["path"] == str(p) and _cache["mtime"] == mtime:
        return _cache["data"]
    out: dict[str, list[dict]] = {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        raw = doc.get("entries", []) if isinstance(doc, dict) else []
    except (OSError, ValueError):
        logger.exception("etf_distribution: cannot read %s", p)
        return {}
    for e in raw:
        errs = validate_entry(e)
        if errs:
            logger.warning("etf_distribution: skip invalid entry %s: %s", (e or {}).get("symbol") if isinstance(e, dict) else e, errs)
            continue
        out.setdefault(str(e["symbol"]).upper(), []).append(e)
    for v in out.values():
        v.sort(key=lambda x: x["ex_date"])
    _cache.update({"path": str(p), "mtime": mtime, "data": out})
    return out
