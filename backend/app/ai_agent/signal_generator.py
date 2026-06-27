"""AI trading signal generation based on technical indicators."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from ..analysis import TechnicalAnalyzer
from ..crawler.stock_price import StockPriceCrawler

DEFAULT_SYMBOLS = ["2330", "2454", "2317", "2308", "6505", "2412"]

# Common stock names for quick lookup (avoid API call per signal)
STOCK_NAMES = {
    "2330": "台積電", "2454": "聯發科", "2317": "鴻海",
    "2308": "台達電", "6505": "台塑化", "2412": "中華電",
    "2881": "富邦金", "2882": "國泰金", "2891": "中信金",
    "2303": "聯電", "3711": "日月光投控", "2886": "兆豐金",
    "2002": "中鋼", "1301": "台塑", "1303": "南亞",
    "2892": "第一金", "2884": "玉山金", "3008": "大立光",
    "2357": "華碩", "2382": "廣達", "2327": "國巨",
    "3034": "聯詠", "2603": "長榮", "2615": "萬海",
    "5871": "中租-KY", "2880": "華南金",
}
_CACHE_TTL_SECONDS = 120
_signal_cache: dict[str, tuple[datetime, list["SignalItem"]]] = {}


class SignalCondition(BaseModel):
    name: str
    met: bool
    value: str


class SignalItem(BaseModel):
    symbol: str
    name_zh: str = ""
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)
    price: float
    reasoning: str
    conditions: list[SignalCondition]
    indicators: dict[str, float | None]
    volume_ratio: float | None = None
    generated_at: datetime


class MarketSnapshot(BaseModel):
    symbol: str
    price: float
    prices: list[float]
    volumes: list[float]
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    prev_macd: float | None
    prev_macd_signal: float | None
    sma20: float | None
    bb_upper: float | None
    bb_lower: float | None
    avg_volume_20: float | None
    volume_ratio: float | None


async def build_market_snapshot(symbol: str) -> MarketSnapshot:
    crawler = StockPriceCrawler()
    analyzer = TechnicalAnalyzer()
    end = date.today()
    start = end - timedelta(days=220)

    df = await crawler.get_price(symbol, str(start), str(end), "1d")
    if df.empty:
        raise ValueError(f"No price data for {symbol}")

    computed = analyzer.compute(
        df.copy(),
        ["ma", "bollinger", "macd", "rsi", "volume"],
        params={
            "ma_periods": [20],
            "bb_period": 20,
            "bb_std": 2,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "rsi_period": 14,
        },
    ).dropna(subset=["close"])

    if len(computed) < 30:
        raise ValueError(f"Insufficient price history for {symbol}")

    latest = computed.iloc[-1]
    previous = computed.iloc[-2]

    avg_volume_20 = _safe_float(computed["volume"].tail(20).mean())
    volume_ratio = None
    if avg_volume_20 and avg_volume_20 > 0:
        volume_ratio = round(float(latest["volume"]) / avg_volume_20, 2)

    return MarketSnapshot(
        symbol=symbol,
        price=round(float(latest["close"]), 2),
        prices=[round(float(v), 4) for v in computed["close"].tail(120).tolist()],
        volumes=[float(v) for v in computed["volume"].tail(120).tolist()],
        rsi=_safe_float(latest.get("rsi14")),
        macd=_safe_float(latest.get("macd_dif")),
        macd_signal=_safe_float(latest.get("macd_dea")),
        prev_macd=_safe_float(previous.get("macd_dif")),
        prev_macd_signal=_safe_float(previous.get("macd_dea")),
        sma20=_safe_float(latest.get("ma20")),
        bb_upper=_safe_float(latest.get("bb_upper")),
        bb_lower=_safe_float(latest.get("bb_lower")),
        avg_volume_20=avg_volume_20,
        volume_ratio=volume_ratio,
    )


def generate_default_signal(snapshot: MarketSnapshot) -> SignalItem:
    buy_score = 0.0
    sell_score = 0.0
    conditions: list[SignalCondition] = []

    rsi_buy = snapshot.rsi is not None and snapshot.rsi < 35
    rsi_sell = snapshot.rsi is not None and snapshot.rsi > 68
    if rsi_buy:
        buy_score += 0.12
    if rsi_sell:
        sell_score += 0.12
    conditions.append(
        SignalCondition(
            name="RSI(14) oversold",
            met=rsi_buy,
            value=f"RSI={_fmt(snapshot.rsi)} < 35",
        )
    )
    conditions.append(
        SignalCondition(
            name="RSI(14) overbought",
            met=rsi_sell,
            value=f"RSI={_fmt(snapshot.rsi)} > 68",
        )
    )

    golden_cross = (
        snapshot.prev_macd is not None
        and snapshot.prev_macd_signal is not None
        and snapshot.macd is not None
        and snapshot.macd_signal is not None
        and snapshot.prev_macd <= snapshot.prev_macd_signal
        and snapshot.macd > snapshot.macd_signal
    )
    death_cross = (
        snapshot.prev_macd is not None
        and snapshot.prev_macd_signal is not None
        and snapshot.macd is not None
        and snapshot.macd_signal is not None
        and snapshot.prev_macd >= snapshot.prev_macd_signal
        and snapshot.macd < snapshot.macd_signal
    )
    if golden_cross:
        buy_score += 0.15
    if death_cross:
        sell_score += 0.15
    conditions.append(
        SignalCondition(
            name="MACD golden cross",
            met=golden_cross,
            value=f"MACD={_fmt(snapshot.macd)}, Signal={_fmt(snapshot.macd_signal)}",
        )
    )
    conditions.append(
        SignalCondition(
            name="MACD death cross",
            met=death_cross,
            value=f"MACD={_fmt(snapshot.macd)}, Signal={_fmt(snapshot.macd_signal)}",
        )
    )

    above_sma20 = snapshot.sma20 is not None and snapshot.price > snapshot.sma20
    if above_sma20:
        buy_score += 0.05
    conditions.append(
        SignalCondition(
            name="Price above SMA20",
            met=above_sma20,
            value=f"Price={snapshot.price:.2f}, SMA20={_fmt(snapshot.sma20)}",
        )
    )

    touch_lower = snapshot.bb_lower is not None and snapshot.price <= snapshot.bb_lower
    touch_upper = snapshot.bb_upper is not None and snapshot.price >= snapshot.bb_upper
    if touch_lower:
        buy_score += 0.08
    if touch_upper:
        sell_score += 0.08
    conditions.append(
        SignalCondition(
            name="Touch Bollinger lower",
            met=touch_lower,
            value=f"Price={snapshot.price:.2f}, Lower={_fmt(snapshot.bb_lower)}",
        )
    )
    conditions.append(
        SignalCondition(
            name="Touch Bollinger upper",
            met=touch_upper,
            value=f"Price={snapshot.price:.2f}, Upper={_fmt(snapshot.bb_upper)}",
        )
    )

    volume_confirm = snapshot.volume_ratio is not None and snapshot.volume_ratio > 1.5
    if volume_confirm:
        if buy_score > sell_score:
            buy_score += 0.05
        elif sell_score > buy_score:
            sell_score += 0.05
    conditions.append(
        SignalCondition(
            name="Volume confirmation",
            met=volume_confirm,
            value=f"Volume ratio={_fmt(snapshot.volume_ratio)}x",
        )
    )

    signal: Literal["BUY", "SELL", "HOLD"] = "HOLD"
    dominant_score = max(buy_score, sell_score)
    if buy_score > sell_score and buy_score >= 0.15:
        signal = "BUY"
    elif sell_score > buy_score and sell_score >= 0.15:
        signal = "SELL"

    confidence = 0.5 if signal == "HOLD" else min(0.99, round(0.5 + dominant_score, 2))

    met_reasons = [condition.name for condition in conditions if condition.met]
    if not met_reasons:
        reasoning = "No strong technical edge detected from the configured rule set."
    else:
        reasoning = "; ".join(met_reasons[:4])

    return SignalItem(
        symbol=snapshot.symbol,
        name_zh=STOCK_NAMES.get(snapshot.symbol, ""),
        signal=signal,
        confidence=confidence,
        price=snapshot.price,
        reasoning=reasoning,
        conditions=conditions,
        indicators={
            "rsi14": snapshot.rsi,
            "macd": snapshot.macd,
            "macd_signal": snapshot.macd_signal,
            "sma20": snapshot.sma20,
            "bb_upper": snapshot.bb_upper,
            "bb_lower": snapshot.bb_lower,
        },
        volume_ratio=snapshot.volume_ratio,
        generated_at=datetime.utcnow(),
    )


async def generate_signals(
    symbols: list[str] | None = None,
    signal_type: Literal["ALL", "BUY", "SELL", "HOLD"] = "ALL",
    rule_id: str = "default",
) -> list[SignalItem]:
    target_symbols = symbols or DEFAULT_SYMBOLS
    cache_key = f"{rule_id}|{','.join(target_symbols)}"
    cached = _signal_cache.get(cache_key)
    now = datetime.utcnow()
    if cached and (now - cached[0]).total_seconds() < _CACHE_TTL_SECONDS:
        results = cached[1]
    else:
        results: list[SignalItem] = []
        for symbol in target_symbols:
            try:
                snapshot = await build_market_snapshot(symbol)
                if rule_id == "default":
                    item = generate_default_signal(snapshot)
                else:
                    from ..signal_rules.engine import rule_engine

                    item = rule_engine.execute_rule(rule_id, snapshot)
                results.append(item)
            except Exception as exc:
                results.append(
                    SignalItem(
                        symbol=symbol,
                        name_zh=STOCK_NAMES.get(symbol, ""),
                        signal="HOLD",
                        confidence=0.0,
                        price=0.0,
                        reasoning=str(exc),
                        conditions=[
                            SignalCondition(
                                name="Data fetch",
                                met=False,
                                value=str(exc),
                            )
                        ],
                        indicators={},
                        volume_ratio=None,
                        generated_at=now,
                    )
                )
        _signal_cache[cache_key] = (now, results)

    if signal_type == "ALL":
        return results
    return [item for item in results if item.signal == signal_type]


async def get_alpha_scores(
    symbols: list[str] | None = None,
    rule_id: str = "default",
) -> list[dict[str, float | str]]:
    """Return per-factor alpha scores (技術面, 法人籌碼, 情緒面, 基本面, 量能)."""
    signals = await generate_signals(symbols=symbols, rule_id=rule_id)

    # Aggregate factor scores across all symbols
    factor_scores = {
        "technical": 0.0,
        "institutional": 0.0,
        "sentiment": 0.0,
        "fundamental": 0.0,
        "volume": 0.0,
    }

    for item in signals:
        for condition in item.conditions:
            met_val = 1.0 if condition.met else 0.0
            name_lower = condition.name.lower()
            if "rsi" in name_lower or "macd" in name_lower or "sma" in name_lower or "bollinger" in name_lower:
                factor_scores["technical"] = max(factor_scores["technical"], met_val * item.confidence)
            if "volume" in name_lower:
                factor_scores["volume"] = max(factor_scores["volume"], met_val * item.confidence)

        # Sentiment from price position relative to Bollinger Bands
        if item.indicators.get("bb_upper") and item.indicators.get("bb_lower"):
            bb_range = item.indicators["bb_upper"] - item.indicators["bb_lower"]
            if bb_range > 0:
                position = (item.price - item.indicators["bb_lower"]) / bb_range
                factor_scores["sentiment"] = max(factor_scores["sentiment"], round(position, 2))

    # For institutional & fundamental, use a heuristic from signal confidence
    avg_confidence = sum(s.confidence for s in signals) / max(1, len(signals)) if signals else 0
    factor_scores["institutional"] = round(avg_confidence * 0.75, 2)
    factor_scores["fundamental"] = round(avg_confidence * 0.6, 2)

    return [
        {"key": key, "value": round(score * 100)}
        for key, score in factor_scores.items()
    ]


def clear_signal_cache() -> None:
    _signal_cache.clear()


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 2)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"
