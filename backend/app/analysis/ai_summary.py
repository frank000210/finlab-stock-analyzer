"""個股 AI 摘要（W2 試點）。

核心設計原則——**LLM 只解讀，不產生數字**：
所有數字都由網站既有模組算好後放進 prompt，LLM 的工作只是「把這些數字
串成人話、指出矛盾、點出該注意的風險」。這是金融應用防幻覺的根本作法：
模型沒有機會編造數據，因為它拿到的就是最終數字，且被明令不得引用未提供
的資訊。

其次是不得給投資建議：prompt 硬性約束 + 輸出後檢查，違規時附加提醒。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是台股個股分析助理，服務對象是有基本財經常識的個人投資人。

嚴格規則（違反即為錯誤輸出）：
1. 只能使用使用者訊息中提供的數據。絕對禁止引用、推算或編造任何未提供的
   數字（包含股價、財報數字、目標價、產業數據）。
2. 不得提供投資建議：不說買進/賣出/加碼/減碼/該進場/該停損，也不預測漲跌
   或給目標價。只做「現況描述」與「風險提示」。
3. 若數據之間互相矛盾（例如營收成長但獲利衰退），必須明確指出矛盾點，並
   說明「該去查證什麼」，而不是自行猜測原因後當成結論陳述。
4. 資料若標明為推估值、樣本不足或有時間差，解讀時要一併說明這個限制。

輸出格式（**臺灣用語的繁體中文，不可出現任何簡體字**，總長 350 字以內）：
**現況**：2-3 句話說明這檔目前的狀態
**值得注意**：條列 2-4 點，每點一句話
**待查證**：條列 1-3 點需要使用者自己確認的事項（沒有就寫「無」）"""

_ADVICE_PATTERNS = ("建議買進", "建議賣出", "建議加碼", "建議減碼", "可以買進", "應該買進", "應該賣出")


def _fmt(v, unit: str = "", nd: int = 2) -> str:
    if v is None:
        return "無資料"
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, (int, float)):
        return f"{round(v, nd)}{unit}"
    return f"{v}{unit}"


def _build_user_prompt(sym: str, bundle: dict) -> str:
    """把網站已算好的數據組成 prompt。每一段都標明資料限制。"""
    lines: list[str] = [f"股票代碼：{sym}"]

    sizing = bundle.get("sizing") or {}
    if sizing:
        lines.append(f"名稱：{sizing.get('name', '')}／產業：{sizing.get('industry', '')}")
        lines.append(
            f"股價 {_fmt(sizing.get('price'))} 元；"
            f"ATR(14) 每日波動 {_fmt(sizing.get('atr_pct'), '%')}；"
            f"市值分級 {sizing.get('cap_tier') or '無資料'}"
        )
        if sizing.get("ma200") is not None:
            lines.append(
                f"年線（200日均線）{_fmt(sizing.get('ma200'))}，"
                f"股價{'在年線之上' if sizing.get('above_ma200') else '在年線之下'}，"
                f"年線{'上揚' if sizing.get('ma200_rising') else '走平或下彎'}"
            )
        setup = sizing.get("setup") or {}
        if setup:
            comp = "、".join(f"{c['name']} {c['score']}/{c['max']}（{c['note']}）"
                             for c in setup.get("components", []))
            lines.append(f"進場評分 {setup.get('total')}/100（{setup.get('verdict')}）：{comp}")

    fund = bundle.get("fundamental") or {}
    eps_rows = (fund.get("eps_quarterly") or [])[-6:]
    if eps_rows:
        lines.append("近六季 EPS：" + "、".join(f"{r['quarter']} {r['eps']}元" for r in eps_rows))
    rev_rows = [r for r in (fund.get("revenue_monthly") or []) if r.get("yoy") is not None][-4:]
    if rev_rows:
        lines.append("近四月營收年增率：" + "、".join(f"{r['month']} {r['yoy']}%" for r in rev_rows))
    mg_rows = (fund.get("margins") or [])[-4:]
    if mg_rows:
        lines.append("近四季毛利率／營益率：" + "、".join(
            f"{r['quarter']} {_fmt(r.get('gross_margin'), '%')}／{_fmt(r.get('operating_margin'), '%')}"
            for r in mg_rows))

    turnover = bundle.get("turnover") or {}
    if turnover:
        pct = turnover.get("percentile")
        lines.append(
            f"換手率 {_fmt(turnover.get('turnover_pct'), '%', 3)}"
            + (f"（近 {turnover.get('sample_days')} 日百分位 {pct}%）"
               if pct is not None else "（樣本不足，未計算百分位）")
            + "。註：換手率以已發行股數估算，非流通股數。"
        )

    chip = bundle.get("chip_summary") or {}
    if chip:
        weeks = chip.get("recent_weeks") or []
        trend = (f"，最近一週變化 {weeks[-1]['mega_pct_change']:+}%" if weeks else
                 "，但週變化資料不足、無法判斷趨勢方向")
        lines.append(
            f"千張大戶持股 {_fmt(chip.get('mega_pct'), '%')}、散戶持股 "
            f"{_fmt(chip.get('retail_pct'), '%')}{trend}。"
            f"籌碼判定：{chip.get('verdict')}（{chip.get('verdict_description')}）。"
            "註：集保資料每週公布一次，與當日股價非同一時點。"
        )

    lights = bundle.get("market_lights") or {}
    combined = lights.get("combined") or {}
    if combined:
        lines.append(f"大盤體制：{combined.get('label')}（信心度 {combined.get('confidence')}）"
                     f"——{combined.get('narrative', '')}")

    return "\n".join(lines)


async def build_ai_summary(symbol: str) -> dict:
    """組裝數據 → 呼叫 LLM → 回傳摘要。快取 6 小時（來源多為日頻資料）。"""
    from ..api.analysis import get_turnover
    from ..api.chip import get_chip_summary
    from ..api.risk import position_sizing
    from ..crawler.fundamental import FundamentalCrawler
    from ..db.cache import get_cache, set_cache
    from ..llm import LLMUnavailable, llm_complete
    from datetime import date, timedelta

    cache_key = f"ai_summary:v1:{symbol}:{date.today().isoformat()}"
    try:
        cached = await get_cache(cache_key)
        if cached:
            return {**cached, "cached": True}
    except Exception:
        pass

    end = date.today()

    async def _safe(coro, unwrap_data: bool = True):
        try:
            r = await coro
            return (r.get("data") if unwrap_data and isinstance(r, dict) else r) or {}
        except Exception:
            return {}

    async def _fund():
        try:
            return await FundamentalCrawler().get_financial_statements(
                symbol, (end - timedelta(days=730)).isoformat(), end.isoformat())
        except Exception:
            return {}

    async def _rev():
        try:
            return await FundamentalCrawler().get_monthly_revenue(
                symbol, (end - timedelta(days=460)).isoformat(), end.isoformat())
        except Exception:
            return []

    from .market_lights import build_market_lights

    sizing, turnover, chip, fin, rev, lights = await asyncio.gather(
        _safe(position_sizing(symbol, lookback_days=365)),
        _safe(get_turnover(symbol)),
        _safe(get_chip_summary(symbol)),
        _fund(),
        _rev(),
        _safe(build_market_lights(), unwrap_data=False),
    )

    bundle = {
        "sizing": sizing,
        "turnover": turnover,
        "chip_summary": chip,
        "fundamental": {**(fin or {}), "revenue_monthly": rev or []},
        "market_lights": lights,
    }
    user_prompt = _build_user_prompt(symbol, bundle)

    # max_tokens 要含 reasoning token：實測 minimax-m2.5 光推理就用掉約 400，
    # 設 900 會讓正文寫到一半被截斷，故拉到 1800。
    text = await llm_complete(SYSTEM_PROMPT, user_prompt, max_tokens=1800, temperature=0.3)

    # 輸出檢查（防越界給建議）：偵測到就附加提醒，而不是丟棄整段回應。
    if any(p in text for p in _ADVICE_PATTERNS):
        logger.warning("AI summary for %s contained advice-like wording", symbol)
        text += "\n\n（系統提醒：本摘要僅為數據解讀，請勿視為投資建議。）"

    result = {
        "symbol": symbol,
        "summary": text,
        "as_of": sizing.get("as_of") or end.isoformat(),
        "model_note": "由 AI 依網站既有數據生成；所有數字均來自網站計算結果，AI 僅負責解讀。",
        "cached": False,
    }
    try:
        await set_cache(cache_key, result, "ai_summary")
    except Exception:
        pass
    return result
