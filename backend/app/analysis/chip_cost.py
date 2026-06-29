"""主力成本線與籌碼集中度估算 (金睿 G股團長 籌碼面風格).

從已取得的法人買賣超與量價資料，估算：
- 主力估計成本線：以法人「買超日」淨買量加權的成交均價 (近似主力進場成本)
- 現價乖離率：現價相對主力成本的乖離，判斷主力獲利或套牢
- 籌碼集中度：區間法人累積淨買超佔總成交量比重 (籌碼是否集中於主力)

不需額外抓取資料，直接複用 analyze_major_players 的結果。
"""

from __future__ import annotations


def compute_major_cost(major: dict | None) -> dict | None:
    """Estimate major-player cost line, price deviation, and chip concentration."""
    if not major:
        return None
    vp = (major.get("volume_price") or {}).get("indicators", [])
    inst = major.get("institutional_flow") or {}
    if not vp:
        return None

    close_map = {d["date"]: d["close"] for d in vp}
    vol_map = {d["date"]: d["volume"] for d in vp}
    foreign = {d["date"]: d["net"] for d in inst.get("foreign", [])}
    trust = {d["date"]: d["net"] for d in inst.get("trust", [])}
    dealer = {d["date"]: d["net"] for d in inst.get("dealer", [])}

    dates = sorted(close_map)
    if not dates:
        return None

    buy_shares = 0.0
    buy_cost = 0.0
    cum_net = 0.0
    total_vol = 0.0

    for dt in dates:
        close = close_map[dt]
        net = foreign.get(dt, 0) + trust.get(dt, 0) + dealer.get(dt, 0)
        vol = vol_map.get(dt, 0) or 0
        total_vol += vol
        cum_net += net
        if net > 0:
            buy_shares += net
            buy_cost += net * close

    last_close = close_map[dates[-1]]
    cost = round(buy_cost / buy_shares, 2) if buy_shares > 0 else None
    deviation = round((last_close - cost) / cost * 100, 2) if cost else None

    # 籌碼集中度：法人累積淨買超 / 區間總成交量 (帶正負號)
    concentration = round(cum_net / total_vol * 100, 2) if total_vol > 0 else 0.0

    # 主力成本判讀
    if cost is None:
        cost_verdict = "資料不足"
        cost_desc = "區間內法人無明顯買超，無法估算主力成本。"
        cost_tone = "flat"
    elif deviation is not None and deviation > 5:
        cost_verdict = "主力獲利"
        cost_desc = f"現價高於主力估計成本 {deviation:.1f}%，主力處於獲利區，留意調節賣壓。"
        cost_tone = "down"
    elif deviation is not None and deviation < -5:
        cost_verdict = "主力套牢"
        cost_desc = f"現價低於主力估計成本 {abs(deviation):.1f}%，主力帳面套牢，後續可能有護盤或停損。"
        cost_tone = "up"
    else:
        cost_verdict = "成本附近"
        cost_desc = "現價貼近主力估計成本，多空成本相當，觀察突破方向。"
        cost_tone = "flat"

    # 集中度判讀
    if concentration >= 3:
        conc_verdict = "高度集中(買方)"
        conc_desc = f"區間法人淨買超佔成交量 {concentration:.1f}%，籌碼明顯流入主力。"
    elif concentration <= -3:
        conc_verdict = "高度集中(賣方)"
        conc_desc = f"區間法人淨賣超佔成交量 {abs(concentration):.1f}%，主力持續調節出貨。"
    elif abs(concentration) < 1:
        conc_verdict = "籌碼分散"
        conc_desc = "法人進出有限，籌碼以市場換手為主。"
    else:
        conc_verdict = "溫和流入" if concentration > 0 else "溫和流出"
        conc_desc = f"區間法人淨{'買' if concentration > 0 else '賣'}超佔成交量 {abs(concentration):.1f}%。"

    return {
        "cost": cost,
        "last_close": last_close,
        "deviation": deviation,
        "cost_verdict": cost_verdict,
        "cost_description": cost_desc,
        "cost_tone": cost_tone,
        "concentration": concentration,
        "conc_verdict": conc_verdict,
        "conc_description": conc_desc,
        "cum_net": int(cum_net),
    }
