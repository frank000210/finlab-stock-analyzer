"""待驗主張 C1–C3：「主力成本乖離 / 籌碼集中度」判讀有沒有預測力？

被驗證的是網站現在實際顯示給使用者的判讀（backend/app/analysis/chip_cost.py）：
  C1 乖離率 < -5%  →「主力套牢」，文案暗示後續可能護盤（tone=up）
  C2 乖離率 > +5%  →「主力獲利」，文案暗示留意調節賣壓（tone=down）
  C3 集中度 >= +3% →「籌碼明顯流入主力」；<= -3% →「持續調節出貨」

做法（對應課程「配對驗證」與「五項回測陷阱」）：
  * 每個交易日 t，只用 t 當天以前 100 個日曆天的資料，照 compute_major_cost 的公式
    重算 cost / deviation / concentration（無前視偏差）。門檻沿用網站現值，不調參。
  * 之後 5 / 10 / 20 個交易日的報酬，與「同一檔股票所有日子」的無條件平均比較（超額報酬），
    避免把多頭期間的整體漂移誤當成訊號效果。
  * 重疊視窗會讓樣本看起來比實際多：另提供「同檔同桶、事件間隔 >= H 日」的稀疏樣本統計。

已知限制（結果解讀時必須帶著）：
  * 股票池是「現在」的大型權值股 → 存活者偏差。
  * 價格是未還原收盤價 → 除息日會讓所有桶同量低估，超額報酬已部分抵銷。
  * 沒計入交易成本。
  * 區間只有一個多頭為主的市場環境，不代表空頭表現。

用法：
  FINMIND_TOKEN=... python scripts/claims/validate_major_cost.py [--start 2022-01-01] [--out report.md]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

UNIVERSE = [
    "2330", "2317", "2454", "2308", "2303", "2412", "2881", "2882", "2891", "2886",
    "1301", "1303", "2002", "2603", "3711", "2382", "2357", "3008", "2379", "2345",
    "1216", "2912", "5880", "2884", "2885", "6505", "3034", "2327", "4938", "2301",
]
HORIZONS = (5, 10, 20)
WINDOW_DAYS = 100  # analyze_major_players: start = end - (days + 10), days=90
API = "https://api.finmindtrade.com/api/v4/data"


def fetch(dataset: str, symbol: str, start: str, end: str, token: str, cache: Path) -> pd.DataFrame:
    path = cache / f"{dataset}_{symbol}_{start}_{end}.json"
    if path.exists():
        return pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))
    q = urllib.parse.urlencode(
        {"dataset": dataset, "data_id": symbol, "start_date": start, "end_date": end, "token": token}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f"{API}?{q}", timeout=60) as r:
                body = json.load(r)
            break
        except Exception as exc:  # noqa: BLE001 - 網路抖動重試，最後一次才放棄
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    if body.get("status") != 200:
        # 訊息可能含額度資訊，但不含 token，可以安全印出。
        raise RuntimeError(f"FinMind {dataset} {symbol}: {body.get('msg')}")
    path.write_text(json.dumps(body["data"], ensure_ascii=False), encoding="utf-8")
    return pd.DataFrame(body["data"])


def daily_net(inst: pd.DataFrame) -> pd.Series:
    """與 major_players._analyze_institutional 相同的分類：外資+投信+自營商淨買超。"""
    if inst.empty:
        return pd.Series(dtype=float)
    net = inst["buy"].astype(float) - inst["sell"].astype(float)
    name = inst["name"].astype(str)
    keep = (
        name.str.contains("外資|Foreign|投信|Investment|自營|Dealer", regex=True)
    )
    s = net[keep].groupby(inst.loc[keep, "date"]).sum()
    s.index = pd.to_datetime(s.index)
    return s


def build_signals(price: pd.DataFrame, net: pd.Series) -> pd.DataFrame:
    price = price.copy()
    # FinMind 對停牌日給 close=0，會讓報酬變成 inf/-100%，先排除。
    price = price[price["close"].astype(float) > 0]
    price["date"] = pd.to_datetime(price["date"])
    price = price.sort_values("date").set_index("date")
    close = price["close"].astype(float)
    vol = price["Trading_Volume"].astype(float)
    netd = net.reindex(close.index).fillna(0.0)

    pos = netd.clip(lower=0.0)
    num = (pos * close).rolling(f"{WINDOW_DAYS}D").sum()
    den = pos.rolling(f"{WINDOW_DAYS}D").sum()
    cost = num / den.where(den > 0)
    deviation = (close - cost) / cost * 100
    conc = netd.rolling(f"{WINDOW_DAYS}D").sum() / vol.rolling(f"{WINDOW_DAYS}D").sum() * 100
    nobs = close.rolling(f"{WINDOW_DAYS}D").count()

    out = pd.DataFrame({"close": close, "deviation": deviation, "conc": conc, "nobs": nobs})
    for h in HORIZONS:
        out[f"fwd{h}"] = close.shift(-h) / close - 1.0
    return out.replace([np.inf, -np.inf], np.nan)


def sparse(df: pd.DataFrame, mask: pd.Series, gap: int) -> pd.DataFrame:
    """同檔同桶：事件間隔至少 gap 個交易日，降低重疊視窗造成的樣本灌水。"""
    rows, last = [], -10**9
    for i, (idx, flag) in enumerate(mask.items()):
        if flag and i - last >= gap:
            rows.append(idx)
            last = i
    return df.loc[rows]


def summarize(frames: dict[str, pd.DataFrame], bucket_fn, label: str) -> list[dict]:
    calendar = sorted(set().union(*[set(f.index) for f in frames.values()]))
    cal_idx = {d: i for i, d in enumerate(calendar)}
    out = []
    for h in HORIZONS:
        col = f"fwd{h}"
        base = {s: f[col].dropna().mean() for s, f in frames.items()}
        base_hit = np.mean(np.concatenate([(f[col].dropna() > 0).to_numpy() for f in frames.values()]))
        allx, thin_x, nall, nthin, hit = [], [], 0, 0, []
        blocks: dict[int, list[float]] = {}
        for s, f in frames.items():
            valid = f.dropna(subset=[col, "deviation", "conc"])
            valid = valid[valid["nobs"] >= 40]
            mask = bucket_fn(valid)
            sel = valid[mask]
            ex = sel[col] - base[s]
            allx.extend(ex.tolist())
            nall += len(sel)
            # 時間區塊：每 h 個交易日一塊，塊內（含跨股票）先平均，吸收同日跨股票相關與重疊視窗。
            for d, v in ex.items():
                blocks.setdefault(cal_idx[d] // h, []).append(v)
            th = sparse(valid, mask, h)
            thin_x.extend((th[col] - base[s]).tolist())
            hit.extend((th[col] > 0).tolist())
            nthin += len(th)
        a, t = np.array(allx), np.array(thin_x)
        bm = np.array([np.mean(v) for v in blocks.values()])
        se_b = bm.std(ddof=1) / math.sqrt(len(bm)) if len(bm) > 1 else float("nan")
        out.append({
            "bucket": label, "h": h,
            "n_all": nall,
            "mean_excess_all_%": round(a.mean() * 100, 2) if len(a) else None,
            "n_sparse": nthin,
            "hit_rate_sparse_%": round(np.mean(hit) * 100, 1) if hit else None,
            "baseline_hit_%": round(base_hit * 100, 1),
            "n_blocks": len(bm),
            "mean_excess_block_%": round(bm.mean() * 100, 2) if len(bm) else None,
            "t_block": round(bm.mean() / se_b, 2) if len(bm) > 1 and se_b else None,
        })
    return out


def _table(res: pd.DataFrame) -> str:
    try:
        return res.to_markdown(index=False)
    except ImportError:  # 沒裝 tabulate 就退回純文字表格
        return res.to_string(index=False)


def main() -> int:
    # Windows 主控台預設 cp1252，印中文會 UnicodeEncodeError。
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    token = os.environ.get("FINMIND_TOKEN", "")
    if not token:
        print("FINMIND_TOKEN not set", file=sys.stderr)
        return 1
    cache = Path(tempfile.gettempdir()) / "finlab_claims"
    cache.mkdir(exist_ok=True)

    fetch_start = (pd.Timestamp(args.start) - pd.Timedelta(days=WINDOW_DAYS + 10)).strftime("%Y-%m-%d")
    end = date.today().isoformat()
    frames: dict[str, pd.DataFrame] = {}
    for sym in UNIVERSE:
        try:
            price = fetch("TaiwanStockPrice", sym, fetch_start, end, token, cache)
            inst = fetch("TaiwanStockInstitutionalInvestorsBuySell", sym, fetch_start, end, token, cache)
        except Exception as exc:  # noqa: BLE001
            print(f"skip {sym}: {exc}", file=sys.stderr)
            continue
        if price.empty or inst.empty:
            print(f"skip {sym}: empty data", file=sys.stderr)
            continue
        sig = build_signals(price, daily_net(inst))
        frames[sym] = sig[sig.index >= pd.Timestamp(args.start)]
        print(f"ok {sym}: {len(frames[sym])} days", file=sys.stderr)

    buckets = [
        ("C1 乖離<-5% (主力套牢)", lambda d: d["deviation"] < -5),
        ("C2 乖離>+5% (主力獲利)", lambda d: d["deviation"] > 5),
        ("對照 乖離在±5%內 (成本附近)", lambda d: d["deviation"].between(-5, 5)),
        ("C3a 集中度>=+3% (流入)", lambda d: d["conc"] >= 3),
        ("C3b 集中度<=-3% (流出)", lambda d: d["conc"] <= -3),
    ]
    rows: list[dict] = []
    for label, fn in buckets:
        rows += summarize(frames, fn, label)
    res = pd.DataFrame(rows)

    n_days = sum(len(f) for f in frames.values())
    lines = [
        f"# 主力成本判讀回測（{args.start} → {end}）",
        "",
        f"股票池 {len(frames)} 檔、共 {n_days} 個股票日。超額報酬 = 事件後 H 日報酬 − 該檔全期無條件平均 H 日報酬。",
        "sparse = 同檔同桶事件間隔 ≥ H 日（命中率用）；block = 每 H 個交易日一塊、塊內跨股票先平均再做 t 檢定（吸收同日跨股票相關與重疊視窗，較保守）。|t_block| < 2 視為不顯著。",
        "",
        _table(res),
    ]
    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
