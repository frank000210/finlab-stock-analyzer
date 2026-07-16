"""市值分級與已發行股數共用邏輯（O1/P5 抽出、Q1 擴充給換手率計算複用）。

市值＝現價×已發行股數，NT$100億分大/中型 vs 小型——這個分級門檻同時被
risk.py（部位風控/觀察清單）跟 analysis.py（換手率）用來動態調整「異常」
的判定標準，所以獨立成一個不依賴任何 API router 的模組，避免 router 之間
互相 import。
"""

CAP_TIER_THRESHOLD = 1e10  # NT$100億


def classify_cap_tier(market_cap: float) -> str:
    return "大型/中型" if market_cap >= CAP_TIER_THRESHOLD else "小型"


async def get_shares_outstanding(symbol: str, start_iso: str, end_iso: str) -> float | None:
    """已發行股數（股）。非台股或資料取不到時回傳 None。"""
    from ..crawler.finmind_client import FinMindClient
    from ..data.us_symbols import is_tw_symbol

    if not is_tw_symbol(symbol):
        return None
    try:
        sh = await FinMindClient().get_shares_outstanding(symbol, start_iso, end_iso)
        if sh is not None and not sh.empty and "NumberOfSharesIssued" in sh.columns:
            return float(sh.sort_values("date")["NumberOfSharesIssued"].iloc[-1])
    except Exception:
        pass
    return None


async def market_cap_tier(symbol: str, price: float, start_iso: str, end_iso: str) -> tuple[float | None, str | None]:
    """市值＝現價×已發行股數，NT$100億分大/中型 vs 小型。非台股或資料取不到
    時回傳 (None, None)，呼叫端不特別處理。
    """
    shares = await get_shares_outstanding(symbol, start_iso, end_iso)
    if shares is None:
        return None, None
    market_cap = price * shares
    return market_cap, classify_cap_tier(market_cap)
