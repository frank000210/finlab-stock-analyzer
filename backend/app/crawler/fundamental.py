"""Fundamental data crawler - revenue, EPS, margins, debt ratios."""

import pandas as pd
from typing import Optional
from .finmind_client import FinMindClient


def quarter_label(date_str: str) -> str:
    """'2026-06-30' → '2026Q2'（FinMind 財報的 date 是季底日）。"""
    s = str(date_str)[:10]
    return f"{s[:4]}Q{(int(s[5:7]) - 1) // 3 + 1}"


def pivot_quarters(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """FinMind 財報長表（date/type/value）→ {'2026Q2': {'Revenue': ..., 'EPS': ...}}。

    損益表、資產負債表、現金流量表都是這個形狀。同一季若有多個 date
    （例如補送），後面的覆蓋前面的。
    """
    out: dict[str, dict[str, float]] = {}
    if df is None or df.empty or not {"date", "type", "value"} <= set(df.columns):
        return out
    for _, row in df.sort_values("date").iterrows():
        try:
            value = float(row["value"])
        except (TypeError, ValueError):
            continue
        out.setdefault(quarter_label(row["date"]), {})[str(row["type"])] = value
    return out


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
                # FinMind 損益表沒有 "NetIncome" 欄位（以前讀它，net_margin 永遠是 None）；
                # 稅後淨利是 IncomeAfterTaxes（金融保險業是 IncomeAfterTax）。
                net = metrics.get("IncomeAfterTaxes", metrics.get("IncomeAfterTax", metrics.get("NetIncome", 0)))
                revenue = metrics.get("Revenue", 1)

                if revenue and float(revenue) > 0:
                    rev = float(revenue)
                    margins_data.append({
                        "quarter": quarter,
                        "gross_margin": round(float(gross) / rev * 100, 2) if gross else None,
                        "operating_margin": round(float(operating) / rev * 100, 2) if operating else None,
                        "net_margin": round(float(net) / rev * 100, 2) if net else None,
                    })

                # 損益表沒有負債比（以前讀 "DebtRatio"，永遠是空的）：負債比由
                # get_debt_ratios() 用資產負債表算，這裡保留欄位維持回傳格式。

        return {
            "eps_quarterly": eps_data,
            "margins": margins_data,
            "debt_ratios": debt_data,
        }

    async def get_debt_ratios(
        self, symbol: str, start: str, end: str
    ) -> list[dict]:
        """負債比（%）＝ 負債總額 ÷ 資產總額，逐季，用資產負債表算。"""
        df = await self.finmind.get_balance_sheet(symbol, start, end)
        rows = []
        for quarter, m in sorted(pivot_quarters(df).items()):
            liabilities, assets = m.get("Liabilities"), m.get("TotalAssets")
            if liabilities is not None and assets and assets > 0:
                rows.append({"quarter": quarter, "debt_ratio": round(liabilities / assets * 100, 2)})
        return rows
