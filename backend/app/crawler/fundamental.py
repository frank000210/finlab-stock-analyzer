"""Fundamental data crawler - revenue, EPS, margins, debt ratios."""

import pandas as pd
from typing import Optional
from .finmind_client import FinMindClient


class FundamentalCrawler:
    """Fetches fundamental financial data for a stock."""

    def __init__(self, finmind_token: Optional[str] = None):
        self.finmind = FinMindClient(token=finmind_token)

    async def get_monthly_revenue(
        self, symbol: str, start: str, end: str
    ) -> list[dict]:
        """Get monthly revenue with YoY growth."""
        df = await self.finmind.get_monthly_revenue(symbol, start, end)
        if df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            entry = {
                "month": f"{row.get('revenue_year', '')}-{int(row.get('revenue_month', 0)):02d}",
                "revenue": row.get("revenue", 0),
                "yoy": row.get("revenue_growth_rate", 0),
            }
            result.append(entry)
        return result

    async def get_financial_statements(
        self, symbol: str, start: str, end: str
    ) -> dict:
        """Get EPS, margins, debt ratios from quarterly financials."""
        df = await self.finmind.get_financial_statements(symbol, start, end)
        if df.empty:
            return {"eps_quarterly": [], "margins": [], "debt_ratios": []}

        eps_data = []
        margins_data = []
        debt_data = []

        # Group by quarter
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df["quarter"] = df["date"].dt.to_period("Q").astype(str)

            for quarter, group in df.groupby("quarter"):
                metrics = dict(zip(
                    group.get("type", pd.Series()),
                    group.get("value", pd.Series())
                ))

                eps = metrics.get("EPS", 0)
                if eps:
                    eps_data.append({"quarter": quarter, "eps": float(eps)})

                gross = metrics.get("GrossProfit", 0)
                operating = metrics.get("OperatingIncome", 0)
                net = metrics.get("NetIncome", 0)
                revenue = metrics.get("Revenue", 1)

                if revenue and float(revenue) > 0:
                    rev = float(revenue)
                    margins_data.append({
                        "quarter": quarter,
                        "gross_margin": round(float(gross) / rev * 100, 2) if gross else None,
                        "operating_margin": round(float(operating) / rev * 100, 2) if operating else None,
                        "net_margin": round(float(net) / rev * 100, 2) if net else None,
                    })

                debt_ratio = metrics.get("DebtRatio", None)
                if debt_ratio:
                    debt_data.append({
                        "quarter": quarter,
                        "debt_ratio": float(debt_ratio),
                    })

        return {
            "eps_quarterly": eps_data,
            "margins": margins_data,
            "debt_ratios": debt_data,
        }
