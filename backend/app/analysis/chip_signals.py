"""進階籌碼訊號 (金睿 G股團長 風格).

複用 analyze_major_players 的法人動向與融資資料，產生兩個進階訊號：
- 外資 + 投信「同步買超」訊號：兩大主力法人同日同向買進，視為主力同步進場
- 融資維持率估算與斷頭風險：以融資餘額增加日加權估算融資戶平均成本，
  推估整戶維持率與斷頭價，評估融資追繳 / 斷頭賣壓風險

兩者皆不需額外抓取資料。
"""

from __future__ import annotations

# 台灣信用交易參數
MARGIN_LOAN_RATIO = 0.6          # 上市股票融資成數 (借六成、自備四成)
MARGIN_CALL_RATIO = 130.0        # 券商追繳/斷頭整戶維持率警戒線 (%)
MARGIN_INITIAL_RATIO = 1 / MARGIN_LOAN_RATIO * 100  # 初始維持率 ≈ 166.7%


def compute_sync_buy(major: dict | None, window: int = 20) -> dict | None:
    """外資 + 投信同步買超訊號。

    偵測區間內外資與投信「同日同向買超」的天數與目前連續同步買的天數，
    判斷兩大主力法人是否同步進場（較單一法人買超更強的訊號）。
    """
    if not major:
        return None
    inst = major.get("institutional_flow") or {}
    foreign = {d["date"]: d["net"] for d in inst.get("foreign", [])}
    trust = {d["date"]: d["net"] for d in inst.get("trust", [])}
    if not foreign or not trust:
        return None

    dates = sorted(set(foreign) & set(trust))
    if not dates:
        return None
    recent = dates[-window:]

    sync_buy_days = 0
    sync_sell_days = 0
    daily = []
    for dt in recent:
        f = foreign.get(dt, 0)
        t = trust.get(dt, 0)
        both_buy = f > 0 and t > 0
        both_sell = f < 0 and t < 0
        if both_buy:
            sync_buy_days += 1
        elif both_sell:
            sync_sell_days += 1
        daily.append({"date": dt, "foreign": int(f), "trust": int(t),
                      "sync": "buy" if both_buy else "sell" if both_sell else "none"})

    # 目前連續同步買超天數 (由近往遠數)
    sync_streak = 0
    for row in reversed(daily):
        if row["sync"] == "buy":
            sync_streak += 1
        else:
            break

    # 近 5 日外資 / 投信合計淨買超
    last5 = recent[-5:]
    f_sum5 = sum(foreign.get(d, 0) for d in last5)
    t_sum5 = sum(trust.get(d, 0) for d in last5)
    combined5 = int(f_sum5 + t_sum5)

    n = len(recent)
    sync_ratio = round(sync_buy_days / n * 100, 1) if n else 0.0

    if sync_streak >= 3:
        verdict = "主力同步買進"
        tone = "up"
        desc = (f"外資與投信已連續 {sync_streak} 日同步買超，"
                f"近 {n} 日有 {sync_buy_days} 日同步買進，兩大主力法人同向進場，籌碼偏多。")
    elif sync_buy_days >= max(3, n // 3) and f_sum5 > 0 and t_sum5 > 0:
        verdict = "法人同步偏多"
        tone = "up"
        desc = (f"近 {n} 日外資與投信同步買超達 {sync_buy_days} 日（{sync_ratio}%），"
                f"近 5 日合計淨買超 {combined5:,} 股，主力法人同步偏多。")
    elif sync_sell_days >= max(3, n // 3) and f_sum5 < 0 and t_sum5 < 0:
        verdict = "法人同步偏空"
        tone = "down"
        desc = (f"近 {n} 日外資與投信同步賣超達 {sync_sell_days} 日，"
                f"近 5 日合計淨賣超 {abs(combined5):,} 股，主力法人同步調節。")
    else:
        verdict = "無明顯同步"
        tone = "flat"
        desc = (f"近 {n} 日外資與投信同步買 {sync_buy_days} 日、同步賣 {sync_sell_days} 日，"
                "兩大法人未明顯同向，方向分歧。")

    return {
        "verdict": verdict,
        "tone": tone,
        "description": desc,
        "sync_buy_days": sync_buy_days,
        "sync_sell_days": sync_sell_days,
        "sync_streak": sync_streak,
        "sync_ratio": sync_ratio,
        "window": n,
        "foreign_5d": int(f_sum5),
        "trust_5d": int(t_sum5),
        "combined_5d": combined5,
        "daily": daily[-10:],
    }


def compute_margin_ratio(major: dict | None) -> dict | None:
    """融資維持率估算與斷頭風險。

    以「融資餘額增加日」的當日收盤價，依增加量加權，估算融資戶平均成本。
    維持率 ≈ (現價 / 融資估計成本) / 融資成數，斷頭價 = 估計成本 × 融資成數 × 130%。
    """
    if not major:
        return None
    margin = major.get("margin_analysis") or {}
    data = margin.get("data") or []
    vp = (major.get("volume_price") or {}).get("indicators", [])
    if len(data) < 5 or not vp:
        return None

    close_map = {d["date"]: d["close"] for d in vp}

    # 以融資餘額「增加日」收盤價，依增加量加權估算融資平均成本
    add_shares = 0.0
    add_cost = 0.0
    prev_bal = None
    for row in data:
        bal = row.get("margin_balance", 0) or 0
        close = close_map.get(row["date"])
        if prev_bal is not None and close and bal > prev_bal:
            inc = bal - prev_bal
            add_shares += inc
            add_cost += inc * close
        prev_bal = bal

    last_close = vp[-1]["close"]
    latest_balance = data[-1].get("margin_balance", 0) or 0

    if add_shares > 0:
        est_cost = round(add_cost / add_shares, 2)
        cost_basis = "估算自融資增加期間加權均價"
    else:
        # 融資餘額未增加，退而用區間均價當作參考成本
        closes = [close_map[r["date"]] for r in data if r["date"] in close_map]
        est_cost = round(sum(closes) / len(closes), 2) if closes else last_close
        cost_basis = "融資餘額未增加，改用區間均價估算"

    maintenance = round((last_close / est_cost) / MARGIN_LOAN_RATIO * 100, 1) if est_cost else None
    # 斷頭價：現價跌至此價時整戶維持率觸及 130%
    margin_call_price = round(est_cost * MARGIN_LOAN_RATIO * MARGIN_CALL_RATIO / 100, 2) if est_cost else None
    buffer_pct = round((last_close - margin_call_price) / last_close * 100, 1) if margin_call_price and last_close else None

    # 融資餘額近期變化
    bal_5d_ago = data[-6]["margin_balance"] if len(data) >= 6 else data[0]["margin_balance"]
    bal_change = latest_balance - (bal_5d_ago or 0)

    if maintenance is None:
        risk = "資料不足"
        tone = "flat"
        desc = "融資資料不足，無法估算維持率。"
    elif maintenance < MARGIN_CALL_RATIO:
        risk = "斷頭風險高"
        tone = "down"
        desc = (f"估計整戶維持率約 {maintenance}%，已低於 130% 追繳線，"
                f"融資戶面臨追繳/斷頭壓力，留意非理性殺盤與融資減肥。")
    elif maintenance < 150:
        risk = "維持率偏低"
        tone = "down"
        desc = (f"估計整戶維持率約 {maintenance}%，距 130% 斷頭線僅約 {buffer_pct}% 緩衝，"
                "股價再跌易引發融資追繳賣壓。")
    elif maintenance < MARGIN_INITIAL_RATIO + 20:
        risk = "維持率正常"
        tone = "flat"
        desc = (f"估計整戶維持率約 {maintenance}%，接近初始 167%，融資戶尚屬安全，"
                f"斷頭價約 {margin_call_price}（距現價 {buffer_pct}%）。")
    else:
        risk = "融資獲利"
        tone = "up"
        desc = (f"估計整戶維持率約 {maintenance}%，遠高於初始水準，融資戶帳面獲利，"
                "下檔斷頭賣壓風險低。")

    if bal_change > 0:
        bal_trend = f"近 5 日融資餘額增加 {int(bal_change):,}（散戶加碼）"
    elif bal_change < 0:
        bal_trend = f"近 5 日融資餘額減少 {int(abs(bal_change)):,}（融資減肥/獲利了結）"
    else:
        bal_trend = "近 5 日融資餘額持平"

    return {
        "est_cost": est_cost,
        "cost_basis": cost_basis,
        "last_close": last_close,
        "maintenance_ratio": maintenance,
        "margin_call_ratio": MARGIN_CALL_RATIO,
        "margin_call_price": margin_call_price,
        "buffer_pct": buffer_pct,
        "latest_balance": int(latest_balance),
        "balance_change_5d": int(bal_change),
        "balance_trend": bal_trend,
        "risk": risk,
        "tone": tone,
        "description": desc,
    }
