"""Institutional investor (chip) data crawler."""

import pandas as pd
from typing import Optional
from .finmind_client import FinMindClient


class InstitutionalCrawler:
    """Fetches institutional investor trading and margin data."""

    def __init__(self, finmind_token: Optional[str] = None):
        self.finmind = FinMindClient(token=finmind_token)

    async def get_chip_data(
        self, symbol: str, start: str, end: str
    ) -> dict:
        """Get complete chip analysis data."""
        institutional = await self._get_institutional(symbol, start, end)
        margin = await self._get_margin(symbol, start, end)

        return {
            "items": institutional,
            "margin": margin,
            "summary": self._compute_summary(institutional),
        }

    async def _get_institutional(
        self, symbol: str, start: str, end: str
    ) -> list[dict]:
        """Get daily institutional buy/sell data."""
        df = await self.finmind.get_institutional_investors(symbol, start, end)
        if df.empty:
            return []

        # Pivot by date and investor name
        result = []
        if "date" in df.columns and "name" in df.columns:
            for date, group in df.groupby("date"):
                entry = {"date": str(date)}
                for _, row in group.iterrows():
                    name = row.get("name", "")
                    buy = float(row.get("buy", 0))
                    sell = float(row.get("sell", 0))
                    net = buy - sell

                    if "外資" in name or "Foreign" in name:
                        entry["foreign_net_buy"] = net
                    elif "投信" in name or "Investment" in name:
                        entry["investment_trust_net_buy"] = net
                    elif "自營" in name or "Dealer" in name:
                        entry["dealer_net_buy"] = entry.get("dealer_net_buy", 0) + net

                result.append(entry)
        return result

    async def _get_margin(
        self, symbol: str, start: str, end: str
    ) -> list[dict]:
        """Get margin trading data."""
        df = await self.finmind.get_margin_trading(symbol, start, end)
        if df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row.get("date", "")),
                "margin_balance": float(row.get("MarginPurchaseTodayBalance", 0)),
                "short_balance": float(row.get("ShortSaleTodayBalance", 0)),
            })
        return result

    def _compute_summary(self, items: list[dict]) -> dict:
        """Compute chip summary metrics."""
        if not items:
            return {"foreign_buy_streak": 0, "investment_trust_trend": "neutral"}

        # Calculate foreign buy streak
        streak = 0
        for item in reversed(items):
            if item.get("foreign_net_buy", 0) > 0:
                streak += 1
            else:
                break

        # Investment trust trend (last 5 days)
        recent = items[-5:] if len(items) >= 5 else items
        trust_net = sum(i.get("investment_trust_net_buy", 0) for i in recent)
        trust_trend = "buy" if trust_net > 0 else "sell" if trust_net < 0 else "neutral"

        return {
            "foreign_buy_streak": streak,
            "investment_trust_trend": trust_trend,
        }
