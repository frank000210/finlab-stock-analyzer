"""籌碼健診評分 — 綜合 6 面向加權，產出 0-100 分與因子拆解.

複用既有訊號 (集保結構 / 法人動向 / 外資投信同步 / 主力成本 / 融資維持率 / 短線投機)，
不另外抓取資料，純粹整合 chip-analysis 既有欄位。50 分為中性。
"""

from typing import Any, Optional

_WEIGHTS = {
    "集保結構": 1.2,
    "法人動向": 1.5,
    "外資投信同步": 1.0,
    "主力成本": 1.0,
    "融資維持率": 0.8,
    "短線投機": 0.8,
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_chip_health(
    distribution: Optional[dict],
    major: Optional[dict],
    major_cost: Optional[dict],
    sync_buy: Optional[dict],
    margin_ratio: Optional[dict],
    day_trade: Optional[dict],
) -> Optional[dict[str, Any]]:
    """回傳 {score, tone, verdict, factors:[{label, score, note}]} 或 None."""
    factors: list[dict[str, Any]] = []

    def push(label: str, score: float, note: str) -> None:
        factors.append({
            "label": label,
            "score": int(round(_clamp(score, -100, 100))),
            "note": note or "",
        })

    if isinstance(distribution, dict) and distribution.get("score") is not None:
        push("集保結構", distribution["score"], distribution.get("verdict", ""))
    if isinstance(major, dict) and major.get("score") is not None:
        push("法人動向", major["score"], major.get("verdict", ""))
    if isinstance(sync_buy, dict) and sync_buy.get("verdict"):
        v = sync_buy["verdict"]
        s = 60 if "同步買" in v else 40 if "偏多" in v else -50 if "偏空" in v else 0
        push("外資投信同步", s, v)
    if isinstance(major_cost, dict) and major_cost.get("deviation") is not None:
        dev = major_cost["deviation"]
        s = 40 if dev > 5 else -40 if dev < -5 else 0
        push("主力成本", s, major_cost.get("cost_verdict", ""))
    if isinstance(margin_ratio, dict) and margin_ratio.get("maintenance_ratio") is not None:
        risk = margin_ratio.get("risk", "")
        s = -55 if "斷頭" in risk else -25 if "偏低" in risk else 15 if "獲利" in risk else 0
        push("融資維持率", s, risk)
    if isinstance(day_trade, dict) and day_trade.get("ratio_5d") is not None:
        v = day_trade.get("verdict", "")
        s = -40 if "極熱" in v else -20 if "偏熱" in v else 20 if "穩定" in v else 0
        push("短線投機", s, v)

    if not factors:
        return None

    total = 0.0
    wsum = 0.0
    for f in factors:
        w = _WEIGHTS.get(f["label"], 1.0)
        total += f["score"] * w
        wsum += w
    avg = total / wsum if wsum else 0.0
    score_pct = int(round(_clamp(50 + avg / 2, 0, 100)))

    if score_pct >= 65:
        tone, verdict = "up", "籌碼面整體偏多，主力與結構面同步支撐。"
    elif score_pct >= 55:
        tone, verdict = "up", "籌碼面略偏多，多方訊號占優但力道有限。"
    elif score_pct >= 45:
        tone, verdict = "flat", "籌碼面多空拉鋸，方向未明，宜搭配技術面確認。"
    elif score_pct >= 35:
        tone, verdict = "down", "籌碼面略偏空，主力調節或結構鬆動跡象浮現。"
    else:
        tone, verdict = "down", "籌碼面整體偏空，多項指標同步示警，宜保守。"

    return {"score": score_pct, "tone": tone, "verdict": verdict, "factors": factors}
