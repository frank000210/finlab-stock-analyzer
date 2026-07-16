"""Analysis API endpoints."""

from fastapi import APIRouter, Query, HTTPException
from datetime import date, timedelta
from ..crawler import StockPriceCrawler, FundamentalCrawler, InstitutionalCrawler
from ..analysis import TechnicalAnalyzer

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.get("/{symbol}/technical")
async def get_technical_analysis(
    symbol: str,
    indicators: str = Query(default="ma,bollinger,macd,kd,rsi,volume"),
    start: date = Query(default=None),
    end: date = Query(default=None),
    period: str = Query(default="1d"),
):
    """Get technical indicators for a stock."""
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=365)

    try:
        crawler = StockPriceCrawler()
        df = await crawler.get_price(symbol, str(start), str(end), period)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        analyzer = TechnicalAnalyzer()
        ind_list = [i.strip() for i in indicators.split(",")]
        computed = analyzer.compute(df, ind_list)
        latest = analyzer.get_latest_indicators(df, ind_list)

        # Build series
        series = []
        for _, row in computed.iterrows():
            entry = {
                "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            }
            for col in computed.columns:
                if col not in ["date", "open", "high", "low", "close", "volume"]:
                    val = row[col]
                    if val is not None and not (isinstance(val, float) and val != val):
                        entry[col] = round(float(val), 2)
            series.append(entry)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "period": period,
                "indicators": latest,
                "series": series,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/fundamental")
async def get_fundamental(
    symbol: str,
    metrics: str = Query(default="revenue,eps,margins,debt_ratios"),
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    """Get fundamental data."""
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=365 * 3)

    try:
        crawler = FundamentalCrawler()
        result = {}

        metric_list = [m.strip() for m in metrics.split(",")]

        if "revenue" in metric_list:
            result["revenue_monthly"] = await crawler.get_monthly_revenue(
                symbol, str(start), str(end)
            )

        if any(m in metric_list for m in ["eps", "margins", "debt_ratios"]):
            financials = await crawler.get_financial_statements(
                symbol, str(start), str(end)
            )
            if "eps" in metric_list:
                result["eps_quarterly"] = financials["eps_quarterly"]
            if "margins" in metric_list:
                result["margins"] = financials["margins"]
            if "debt_ratios" in metric_list:
                result["debt_ratios"] = financials["debt_ratios"]

        return {"success": True, "data": {"symbol": symbol, **result}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_TURNOVER_MIN_TRADING_DAYS = 20  # R3：樣本太少時百分位排名沒有統計意義


@router.get("/{symbol}/turnover")
async def get_turnover(symbol: str):
    """換手率分析（Q1）：換手率＝當日成交量 ÷ 已發行股數，衡量籌碼流動的
    活躍程度。用已發行股數而非真正的流通股數（台股沒有公開的自由流通量
    資料源），跟主力成本估算同一個誠信慣例：標明是近似值；已發行股數本身
    也只在增資/減資/初次公開發行等事件時才會變動，不是每天更新。

    只回傳近 60 個交易日的序列＋今天在這段期間內的百分位排名，讓前端可以
    用「相對自己歷史」而不是全市場統一門檻來判斷是否異常——不同股本大小
    的正常換手率基準差很多，套死的門檻沒有意義。樣本不足 20 個交易日時
    （例如新上市股票）percentile 回傳 null，避免用 1-2 筆資料算出無意義
    的「100 百分位」卻用跟正常情況一樣的信心呈現。
    """
    import asyncio

    import pandas as pd
    from datetime import date, timedelta

    from ..analysis.market_cap import classify_cap_tier
    from ..crawler.finmind_client import FinMindClient
    from ..crawler.stock_price import StockPriceCrawler
    from ..data.us_symbols import is_tw_symbol, normalize_symbol

    symbol = normalize_symbol(symbol)
    if not is_tw_symbol(symbol):
        raise HTTPException(status_code=404, detail="換手率僅支援台股（需要已發行股數資料，美股/指數無此資料源）")

    end = date.today()
    start = end - timedelta(days=120)  # 抓夠多日曆天，確保有 60 個交易日

    # R5：價格跟已發行股數是兩個獨立資料源，改併發抓取。
    crawler = StockPriceCrawler()
    df, sh = await asyncio.gather(
        crawler.get_price(symbol, start.isoformat(), end.isoformat(), "1d"),
        FinMindClient().get_shares_outstanding(symbol, start.isoformat(), end.isoformat()),
    )
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"{symbol} 查無價格資料")

    # R3：已發行股數是不定期公布的時間序列（不是每天更新），用整段期間裡
    # 「最新一天」的股數套用到全部歷史交易日會讓增資/減資前的換手率算錯。
    # 改用 merge_asof 依每天當時最近一次已知的股數對齊，較貼近真實情況。
    if sh is None or sh.empty or "NumberOfSharesIssued" not in sh.columns:
        raise HTTPException(status_code=404, detail=f"{symbol} 查無已發行股數資料")
    sh = sh[["date", "NumberOfSharesIssued"]].dropna().sort_values("date")
    sh["date"] = pd.to_datetime(sh["date"])
    shares_latest = float(sh["NumberOfSharesIssued"].iloc[-1])
    if shares_latest <= 0:
        raise HTTPException(status_code=404, detail=f"{symbol} 已發行股數資料異常")

    df = df.sort_values("date").tail(60).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    merged = pd.merge_asof(df, sh, on="date", direction="backward")
    # 價格資料比已發行股數資料更早（asof 對不到）的天數，用最早一筆已知股數
    # 回填——沒有更早的資料可用，這是能做到最接近的近似值。
    merged["NumberOfSharesIssued"] = merged["NumberOfSharesIssued"].ffill().bfill()

    turnover = (merged["volume"].astype(float) / merged["NumberOfSharesIssued"] * 100)
    dates = merged["date"].dt.strftime("%Y-%m-%d").tolist()
    series = [{"date": d, "turnover_pct": round(float(t), 3)} for d, t in zip(dates, turnover)]

    today_pct = float(turnover.iloc[-1])
    # 百分位排名：今天的換手率贏過近 60 日內多少比例的交易日（含自己）。
    # 樣本太少（例如新上市股票）時排名沒有統計意義，回傳 null 而不是硬湊。
    percentile = (
        round(float((turnover <= today_pct).sum()) / len(turnover) * 100, 1)
        if len(turnover) >= _TURNOVER_MIN_TRADING_DAYS
        else None
    )

    price = float(df["close"].iloc[-1])
    market_cap = price * shares_latest
    cap_tier = classify_cap_tier(market_cap)

    return {
        "success": True,
        "data": {
            "symbol": symbol,
            "turnover_pct": round(today_pct, 3),
            "percentile": percentile,
            "sample_days": len(turnover),
            "cap_tier": cap_tier,
            "series": series,
            "as_of": dates[-1],
            "shares_as_of": str(sh["date"].iloc[-1])[:10],
            "source": crawler.last_source,
        },
    }


# 季報法定公告截止日（公開資訊觀測站規定，非預測）：Q1 5/15、Q2 8/14、Q3 11/14、
# 年報(Q4) 次年 3/31。用來估算「下一次財報最晚何時會公告」。
_FIN_DEADLINES = [(5, 15), (8, 14), (11, 14), (3, 31)]


@router.get("/{symbol}/calendar")
async def get_stock_calendar(symbol: str):
    """個股重要日期行事曆（A4）：月營收公告、季報法定截止日、除權息歷史。

    營收/除息為 FinMind 實際歷史資料；「下次公告」為根據公開法規/歷史週期
    的估算，非官方保證日期，事件皆標明 estimated 旗標。
    """
    import asyncio
    from datetime import date, datetime, timedelta

    from ..crawler.finmind_client import FinMindClient

    end = date.today()
    start = end - timedelta(days=400)
    client = FinMindClient()

    async def _revenue_events():
        try:
            df = await client.get_monthly_revenue(symbol, start.isoformat(), end.isoformat())
        except Exception:
            return []
        if df.empty or "create_time" not in df.columns:
            return []
        df = df.sort_values("date")
        events = []
        for _, row in df.tail(6).iterrows():
            disclose = str(row.get("create_time", "") or "").strip()[:10]
            # FinMind 部分較舊資料列缺 create_time：沒有真實公告日就跳過，
            # 不硬湊一個空白/假日期。
            if not disclose or disclose.lower() == "nan":
                continue
            try:
                events.append({
                    "date": disclose, "type": "revenue",
                    "label": f"{int(row['revenue_year'])}年{int(row['revenue_month'])}月營收公告",
                    "estimated": False,
                    "detail": f"營收 {float(row['revenue']) / 1e8:.1f} 億元",
                })
            except Exception:
                continue
        # 下次營收公告：法定次月10日前。從最近一次公告日逐月往後推，直到推出
        # 一個還沒到的日期為止（今天若剛好卡在上次公告日之後、下次之前，只
        # 推一次月份會落在過去，需要繼續往後找）。
        if events:
            next_due = datetime.strptime(events[-1]["date"], "%Y-%m-%d").date()
            for _ in range(3):
                nxt_month = next_due.month % 12 + 1
                nxt_year = next_due.year + (1 if next_due.month == 12 else 0)
                next_due = date(nxt_year, nxt_month, 10)
                if next_due > end:
                    break
            if next_due > end:
                events.append({
                    "date": next_due.isoformat(), "type": "revenue",
                    "label": "下月營收公告（預估，法定 10 日前）", "estimated": True, "detail": "",
                })
        return events

    async def _financial_events():
        try:
            df = await client.get_financial_statements(symbol, start.isoformat(), end.isoformat())
        except Exception:
            return []
        if df.empty or "date" not in df.columns:
            return []
        quarters = sorted(set(str(d)[:10] for d in df["date"]))
        events = [{
            "date": q, "type": "financials",
            "label": "季報期末（財報涵蓋期間結束）", "estimated": False, "detail": "",
        } for q in quarters[-4:]]
        # 下一次法定公告截止日（估算，非官方保證）：四個法定截止日各自算出
        # 「下一次會落在哪一天」，再取全部候選中最近的一個——不能只看列表
        # 裡第一個大於今天的，因為法定截止日不是按年曆順序排列的。
        candidates = []
        for month, day in _FIN_DEADLINES:
            due = date(end.year, month, day)
            if due <= end:
                due = date(end.year + 1, month, day)
            candidates.append(due)
        if candidates:
            due = min(candidates)
            events.append({
                "date": due.isoformat(), "type": "financials",
                "label": "下次財報法定公告截止日（預估）", "estimated": True, "detail": "",
            })
        return events

    async def _dividend_events():
        try:
            df = await client.get_dividend_history(symbol, start.isoformat(), end.isoformat())
        except Exception:
            return []
        if df.empty:
            return []
        events = []
        for _, row in df.tail(4).iterrows():
            ex_date = str(row.get("CashExDividendTradingDate", "") or row.get("StockExDividendTradingDate", "") or "").strip()
            if not ex_date or ex_date.lower() == "nan":
                continue
            cash = row.get("CashEarningsDistribution", 0) or 0
            events.append({
                "date": ex_date, "type": "dividend",
                "label": "現金除息" if float(cash) > 0 else "除權息",
                "estimated": False,
                "detail": f"現金股利 {float(cash):.2f} 元" if float(cash) > 0 else "",
            })
        return events

    try:
        revenue, financials, dividends = await asyncio.gather(
            _revenue_events(), _financial_events(), _dividend_events()
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"行事曆資料取得失敗：{exc}")

    events = sorted(revenue + financials + dividends, key=lambda e: e["date"])
    return {"success": True, "data": {"symbol": symbol, "events": events, "as_of": end.isoformat()}}


@router.get("/{symbol}/chip")
async def get_chip_analysis(
    symbol: str,
    start: date = Query(default=None),
    end: date = Query(default=None),
):
    """Get institutional investor (chip) analysis."""
    if not end:
        end = date.today()
    if not start:
        start = end - timedelta(days=90)

    try:
        crawler = InstitutionalCrawler()
        data = await crawler.get_chip_data(symbol, str(start), str(end))
        return {"success": True, "data": {"symbol": symbol, **data}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
