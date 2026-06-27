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
        """Get monthly revenue with YoY growth (calculated from raw data)."""
        df = await self.finmind.get_monthly_revenue(symbol, start, end)
        if df.empty:
            return []

        # Build a lookup: (year, month) -> revenue for YoY calculation
        revenue_map = {}
        for _, row in df.iterrows():
            year = int(row.get("revenue_year", 0))
            month = int(row.get("revenue_month", 0))
            rev = row.get("revenue", 0)
            if year and month:
                revenue_map[(year, month)] = rev

        result = []
        for _, row in df.iterrows():
            year = int(row.get("revenue_year", 0))
            month = int(row.get("revenue_month", 0))
            rev = row.get("revenue", 0)

            # Calculate YoY: compare with same month last year
            last_year_rev = revenue_map.get((year - 1, month), 0)
            if last_year_rev and last_year_rev > 0:
                yoy = round((rev - last_year_rev) / last_year_rev * 100, 2)
            else:
                yoy = None

            entry = {
                "month": f"{year}-{month:02d}",
                "revenue": rev,
                "yoy": yoy,
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
