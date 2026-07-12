"""社群熱度分析 (Social Media & News Buzz Analysis).

Measures discussion volume and sentiment for a stock across:
- PTT Stock board (批踢踢股板)
- Google News (新聞曝光量)
- Volume-based proxy for market attention
"""

import re
import time
import hashlib
import urllib.parse
import httpx
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional
from ..crawler import StockPriceCrawler


def _format_pub_date(raw: str) -> str:
    """RSS pubDate (RFC 822，如 'Fri, 12 Jul 2026 08:00:00 GMT') 轉成 YYYY-MM-DD；
    格式不明時原樣保留，避免顯示空白讓使用者以為完全沒有日期資訊。
    """
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return raw


def _ptt_date_with_year(md: str) -> str:
    """PTT 列表頁只給 'M/D'（無年份），推回完整日期：若這個月/日比今天晚，
    代表是去年的貼文（列表本身是新到舊排序，不會出現更早的未來日期）。
    """
    if not md or "/" not in md:
        return md
    try:
        month, day = (int(p) for p in md.split("/", 1))
        today = date.today()
        year = today.year
        if (month, day) > (today.month, today.day):
            year -= 1
        return date(year, month, day).isoformat()
    except (TypeError, ValueError):
        return md


# Module-level cache for social data (longer TTL since it's expensive)
_social_cache: dict[str, tuple[float, dict]] = {}
_SOCIAL_CACHE_TTL = 600  # 10 minutes


def _clear_cache() -> int:
    count = len(_social_cache)
    _social_cache.clear()
    return count


try:
    from ..db.memory_cache import register as _register_memory_cache

    _register_memory_cache("social_buzz", lambda: len(_social_cache), _clear_cache)
except Exception:  # registry 不可用時不影響本模組運作
    pass


def _get_social_cached(key: str) -> Optional[dict]:
    entry = _social_cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > _SOCIAL_CACHE_TTL:
        del _social_cache[key]
        return None
    return data


def _set_social_cached(key: str, data: dict) -> None:
    _social_cache[key] = (time.time(), data)
    if len(_social_cache) > 50:
        oldest = min(_social_cache, key=lambda k: _social_cache[k][0])
        del _social_cache[oldest]


# 每日快照持久化：讓熱度分數不再只是「這一刻」的瞬時值，之後可以畫趨勢圖，
# 也讓 trend 判斷能跟這檔股票自己的歷史基準比較，而不是套一個對所有股票
# 都一樣的絕對門檻。寫入失敗（Mongo 不可用）不能讓整個分析跟著失敗，比照
# 本檔案其他資料來源一律 try/except 吞掉。
_BASELINE_LOOKBACK_DAYS = 14
_BASELINE_MIN_SAMPLES = 3


async def _record_snapshot(symbol: str, post_count: int, article_count: int, buzz_score: int) -> None:
    try:
        from ..db.mongodb import get_mongodb
        db = await get_mongodb()
        await db.social_buzz_history.update_one(
            {"symbol": symbol, "date": str(date.today())},
            {"$set": {
                "symbol": symbol,
                "date": str(date.today()),
                "post_count": post_count,
                "article_count": article_count,
                "buzz_score": buzz_score,
                "updated_at": datetime.utcnow(),
            }},
            upsert=True,
        )
    except Exception:
        pass


async def _get_trend_baseline(symbol: str) -> Optional[dict]:
    """近 N 天的 PTT/新聞則數平均，作為判斷「相對上升/下降」的基準。
    樣本不足（新股票或剛上線）回傳 None，呼叫端會退回絕對門檻判斷。
    """
    try:
        from ..db.mongodb import get_mongodb
        db = await get_mongodb()
        cutoff = str(date.today() - timedelta(days=_BASELINE_LOOKBACK_DAYS))
        rows = [
            row async for row in
            db.social_buzz_history.find(
                {"symbol": symbol, "date": {"$gte": cutoff}},
                {"_id": 0, "post_count": 1, "article_count": 1},
            )
        ]
        if len(rows) < _BASELINE_MIN_SAMPLES:
            return None
        return {
            "avg_posts": sum(r.get("post_count", 0) for r in rows) / len(rows),
            "avg_articles": sum(r.get("article_count", 0) for r in rows) / len(rows),
            "sample_days": len(rows),
        }
    except Exception:
        return None


async def get_buzz_history(symbol: str, days: int = 30) -> list[dict]:
    """近 N 天的每日熱度快照，供前端畫趨勢走勢用。"""
    try:
        from ..db.mongodb import get_mongodb
        db = await get_mongodb()
        cutoff = str(date.today() - timedelta(days=days))
        cursor = db.social_buzz_history.find(
            {"symbol": symbol, "date": {"$gte": cutoff}},
            {"_id": 0, "date": 1, "post_count": 1, "article_count": 1, "buzz_score": 1},
        ).sort("date", 1)
        return [row async for row in cursor]
    except Exception:
        return []


async def analyze_social_buzz(symbol: str, stock_name: str = "") -> dict:
    """Analyze social media and news buzz for a stock.

    Args:
        symbol: Stock symbol (e.g., "2330")
        stock_name: Chinese name for search (e.g., "台積電")

    Returns:
        - buzz_score: 0-100 overall buzz level
        - ptt_data: PTT discussion results
        - news_data: News mentions
        - volume_attention: Volume-based attention proxy
        - trend: buzz trend (rising/falling/stable)
    """
    cache_key = hashlib.md5(f"social_{symbol}_{stock_name}".encode()).hexdigest()
    cached = _get_social_cached(cache_key)
    if cached:
        return cached

    # Search terms
    search_terms = [symbol]
    if stock_name:
        search_terms.append(stock_name)

    # Gather data from multiple sources (each wrapped to avoid cascading failures)
    try:
        ptt_result = await _scrape_ptt(search_terms)
    except Exception:
        ptt_result = {"post_count": 0, "posts": [], "sentiment": "neutral", "bullish_count": 0, "bearish_count": 0, "trend": "stable", "source": "PTT 股板"}

    try:
        news_result = await _scrape_news(search_terms)
    except Exception:
        news_result = {"article_count": 0, "articles": [], "trend": "stable", "source": "Google News"}

    try:
        volume_result = await _analyze_volume_attention(symbol)
    except Exception:
        volume_result = {"attention_score": 50, "volume_surge": False, "volume_ratio": 1.0, "vol_increasing": False, "avg_volume_20d": 0, "avg_volume_5d": 0}

    try:
        factcheck_result = await _scrape_factcheck(search_terms)
    except Exception:
        factcheck_result = {"check_count": 0, "items": [], "source": "台灣事實查核中心", "source_url": "https://tfc-taiwan.org.tw/"}

    try:
        finance_news_result = await _scrape_finance_news(search_terms)
    except Exception:
        finance_news_result = {"article_count": 0, "articles": [], "trend": "stable", "source": "台灣財經媒體（鉅亨網／MoneyDJ／CMoney）"}

    # Compute composite buzz score (0-100)
    ptt_score = min(100, ptt_result["post_count"] * 5)  # 20 posts = 100
    news_score = min(100, news_result["article_count"] * 10)  # 10 articles = 100
    finance_score = min(100, finance_news_result["article_count"] * 10)
    vol_score = volume_result.get("attention_score", 0)

    buzz_score = int(ptt_score * 0.30 + news_score * 0.25 + finance_score * 0.15 + vol_score * 0.30)

    # 趨勢判斷：有足夠的歷史快照時，改用「相對於這檔股票自己近14天均值」的比例
    # 判斷（避免權值股天生比小型股容易被判定成"熱度上升"），沒有歷史資料時
    # （功能剛上線或冷門股第一次查）才退回原本的絕對門檻判斷。
    baseline = await _get_trend_baseline(symbol)
    if baseline:
        post_ratio = (ptt_result["post_count"] / baseline["avg_posts"]) if baseline["avg_posts"] > 0 else (2.0 if ptt_result["post_count"] > 0 else 1.0)
        article_ratio = (news_result["article_count"] / baseline["avg_articles"]) if baseline["avg_articles"] > 0 else (2.0 if news_result["article_count"] > 0 else 1.0)
        if post_ratio >= 1.5 or article_ratio >= 1.5:
            trend, trend_label = "rising", "討論度上升中"
        elif post_ratio <= 0.6 and article_ratio <= 0.6:
            trend, trend_label = "falling", "討論度下降中"
        else:
            trend, trend_label = "stable", "討論度穩定"
    elif ptt_result.get("trend") == "rising" or news_result.get("trend") == "rising":
        trend = "rising"
        trend_label = "討論度上升中"
    elif ptt_result.get("trend") == "falling" and news_result.get("trend") == "falling":
        trend = "falling"
        trend_label = "討論度下降中"
    else:
        trend = "stable"
        trend_label = "討論度穩定"

    # Buzz level description
    if buzz_score >= 80:
        level = "極高"
        level_desc = "該股當前為市場焦點，需留意過熱風險"
    elif buzz_score >= 60:
        level = "高"
        level_desc = "討論度明顯高於平常，市場關注度提升"
    elif buzz_score >= 40:
        level = "中等"
        level_desc = "有一定討論度，屬正常範圍"
    elif buzz_score >= 20:
        level = "低"
        level_desc = "討論度偏低，市場關注較少"
    else:
        level = "極低"
        level_desc = "幾乎無人討論，可能為冷門股"

    # Sentiment from PTT
    sentiment = ptt_result.get("sentiment", "neutral")
    if sentiment == "bullish":
        sentiment_label = "偏多（看好意見較多）"
    elif sentiment == "bearish":
        sentiment_label = "偏空（看壞意見較多）"
    else:
        sentiment_label = "中性（多空意見分歧）"

    result = {
        "symbol": symbol,
        "stock_name": stock_name,
        "buzz_score": buzz_score,
        "buzz_level": level,
        "buzz_description": level_desc,
        "trend": trend,
        "trend_label": trend_label,
        "sentiment": sentiment,
        "sentiment_label": sentiment_label,
        "ptt": ptt_result,
        "news": news_result,
        "finance_news": finance_news_result,
        "fact_check": factcheck_result,
        "volume_attention": volume_result,
        "trend_baseline": baseline,
        "updated_at": str(date.today()),
    }

    await _record_snapshot(symbol, ptt_result["post_count"], news_result["article_count"], buzz_score)

    _set_social_cached(cache_key, result)
    return result


def _parse_push_count(raw: str) -> int:
    """PTT 列表頁的推文數不是單純數字：'爆' 代表極熱門（視為 100），
    'X1'~'X9'/'XX' 代表噓多於推（負值，'XX' 代表 -10 以上）。
    """
    raw = (raw or "").strip()
    if raw == "爆":
        return 100
    if raw == "XX":
        return -10
    if raw.startswith("X") and raw[1:].isdigit():
        return -int(raw[1:])
    if raw.isdigit():
        return int(raw)
    return 0


async def _scrape_ptt(search_terms: list[str]) -> dict:
    """Scrape PTT Stock board for discussion volume."""
    posts = []
    bullish_weight = 0
    bearish_weight = 0
    bullish_count = 0
    bearish_count = 0

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            # Search PTT Stock board
            for term in search_terms[:2]:  # Limit to 2 terms
                url = f"https://www.ptt.cc/bbs/Stock/search?q={term}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Cookie": "over18=1",
                }
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue

                html = resp.text
                # 逐篇解析（而非分別用三個平行 regex 陣列配對），避免推文數
                # 遇到非數字格式（'爆'／'X1'）時 findall 漏抓一筆，導致後面每篇
                # 文章的推文數都對應錯欄位。
                blocks = re.findall(r'<div class="r-ent">.*?<div class="mark">.*?</div>\s*</div>', html, re.DOTALL)
                for block in blocks[:20]:
                    title_match = re.search(r'<div class="title">\s*<a href="([^"]+)"[^>]*>(.+?)</a>', block, re.DOTALL)
                    if not title_match:
                        continue  # 已刪除的文章沒有連結
                    href, title = title_match.group(1), title_match.group(2).strip()
                    date_match = re.search(r'<div class="date">\s*(\d+/\d+)', block)
                    push_match = re.search(r'<div class="nrec"><span class="hl f\d">(.*?)</span>', block)
                    push_count = _parse_push_count(push_match.group(1) if push_match else "")

                    posts.append({
                        "title": title,
                        "url": f"https://www.ptt.cc{href}" if href.startswith("/") else href,
                        "date": _ptt_date_with_year(date_match.group(1)) if date_match else "",
                        "push_count": push_count,
                    })

                    # 標題關鍵字判斷多空方向，用推文數（社群認同度）加權，而非
                    # 每篇文章等權重計入——一篇被推爆的看多文，應該比一篇零星
                    # 噓聲的看多文更能代表版上真實情緒。
                    weight = push_count if push_count > 0 else 1
                    title_lower = title.lower()
                    if any(w in title_lower for w in ["多", "漲", "噴", "飛", "強", "利多", "看好", "加碼"]):
                        bullish_count += 1
                        bullish_weight += weight
                    elif any(w in title_lower for w in ["空", "跌", "崩", "慘", "利空", "看壞", "減碼", "出"]):
                        bearish_count += 1
                        bearish_weight += weight

    except Exception:
        pass

    # Deduplicate
    seen_titles = set()
    unique_posts = []
    for p in posts:
        if p["title"] not in seen_titles:
            seen_titles.add(p["title"])
            unique_posts.append(p)

    post_count = len(unique_posts)

    # Sentiment（用推文數加權後的多空聲量比較，而非單純篇數）
    if bullish_weight > bearish_weight * 1.5:
        sentiment = "bullish"
    elif bearish_weight > bullish_weight * 1.5:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    # Trend estimation (based on post density, simplified)
    trend = "stable"
    if post_count >= 15:
        trend = "rising"
    elif post_count <= 3:
        trend = "falling"

    return {
        "post_count": post_count,
        "posts": unique_posts[:10],  # Top 10
        "sentiment": sentiment,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "trend": trend,
        "source": "PTT 股板",
    }


async def _fetch_google_news_rss(query: str, limit: int = 10) -> list[dict]:
    """Fetch + parse a Google News RSS search query into article dicts."""
    articles: list[dict] = []
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return articles
        xml = resp.text
        items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
        for item in items[:limit]:
            title_match = re.search(r"<title>(.*?)</title>", item)
            link_match = re.search(r"<link>(.*?)</link>", item)
            pub_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
            source_match = re.search(r"<source[^>]*>(.*?)</source>", item)
            if title_match:
                articles.append({
                    "title": title_match.group(1).strip(),
                    "url": link_match.group(1).strip() if link_match else "",
                    "published": _format_pub_date(pub_match.group(1).strip() if pub_match else ""),
                    "source": source_match.group(1).strip() if source_match else "Google News",
                })
    return articles


async def _scrape_news(search_terms: list[str]) -> dict:
    """Scrape Google News for recent news articles."""
    articles = []

    try:
        for term in search_terms[:2]:
            # "stock" 是英文字，混在 zh-TW locale 查詢裡對純數字代號完全沒有
            # 消歧效果；改用中文「股票」讓 Google News 用台股語境排序結果。
            articles.extend(await _fetch_google_news_rss(f"{term} 股票"))
    except Exception:
        pass

    # Deduplicate
    seen = set()
    unique_articles = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique_articles.append(a)

    article_count = len(unique_articles)

    # Trend
    trend = "stable"
    if article_count >= 8:
        trend = "rising"
    elif article_count <= 2:
        trend = "falling"

    return {
        "article_count": article_count,
        "articles": unique_articles[:8],
        "trend": trend,
        "source": "Google News",
    }


# 台灣財經專門媒體：這幾家沒有可直接打的公開 RSS/搜尋 API（鉅亨網/MoneyDJ
# 都是 404，Dcard 有 Cloudflare 擋爬蟲），改用 Google News 本身的 site:
# 篩選子句間接取得結構化、有精確發布日期的財經媒體報導，避免自建脆弱的
# per-站台 scraper。
_FINANCE_SITES = "(site:cnyes.com OR site:moneydj.com OR site:cmoney.tw)"


async def _scrape_finance_news(search_terms: list[str]) -> dict:
    """Google News RSS 限定台灣財經媒體站台，補足純新聞搜尋以外的精確度來源。"""
    articles = []

    try:
        for term in search_terms[:2]:
            articles.extend(await _fetch_google_news_rss(f"{term} {_FINANCE_SITES}"))
    except Exception:
        pass

    seen = set()
    unique_articles = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique_articles.append(a)

    article_count = len(unique_articles)
    trend = "stable"
    if article_count >= 5:
        trend = "rising"
    elif article_count <= 1:
        trend = "falling"

    return {
        "article_count": article_count,
        "articles": unique_articles[:8],
        "trend": trend,
        "source": "台灣財經媒體（鉅亨網／MoneyDJ／CMoney）",
    }


async def _scrape_factcheck(search_terms: list[str]) -> dict:
    """Query 台灣事實查核中心 (TFC) WordPress search RSS for related fact checks."""
    items: list[dict] = []
    # 純數字代號會在查核中心全文搜尋裡亂匹配（日期、金額等），只用中文股名查
    name_terms = [t for t in search_terms if not t.isdigit()]
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for term in name_terms[:2]:
                url = f"https://tfc-taiwan.org.tw/?s={term}&feed=rss2"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue
                xml = resp.text
                for item in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)[:6]:
                    title_match = re.search(r"<title>(.*?)</title>", item)
                    link_match = re.search(r"<link>(.*?)</link>", item)
                    pub_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
                    if not title_match or not link_match:
                        continue
                    title = title_match.group(1).strip()
                    # 查核報告標題常見【錯誤】【部分錯誤】【事實釐清】等前綴,抽出當判定結果
                    verdict_match = re.match(r"^[【\[]([^】\]]{1,6})[】\]]", title)
                    items.append({
                        "title": title,
                        "url": link_match.group(1).strip(),
                        "published": _format_pub_date(pub_match.group(1).strip() if pub_match else ""),
                        "verdict": verdict_match.group(1) if verdict_match else "相關文章",
                    })
    except Exception:
        pass

    seen: set[str] = set()
    unique_items = []
    for it in items:
        if it["url"] not in seen:
            seen.add(it["url"])
            unique_items.append(it)

    return {
        "check_count": len(unique_items),
        "items": unique_items[:6],
        "source": "台灣事實查核中心",
        "source_url": "https://tfc-taiwan.org.tw/",
    }


async def _analyze_volume_attention(symbol: str) -> dict:
    """Use volume surge as a proxy for market attention."""
    end = date.today()
    start = end - timedelta(days=60)

    crawler = StockPriceCrawler()
    df = await crawler.get_price(symbol, str(start), str(end), "1d")

    if df.empty or len(df) < 20:
        return {"attention_score": 50, "volume_surge": False}

    df = df.sort_values("date").reset_index(drop=True)

    # Volume ratio: recent 5 days vs 20-day average
    vol_20ma = df["volume"].rolling(20).mean().iloc[-1]
    vol_recent = df["volume"].tail(5).mean()

    if vol_20ma > 0:
        vol_ratio = vol_recent / vol_20ma
    else:
        vol_ratio = 1.0

    # Attention score based on volume
    attention_score = min(100, int(vol_ratio * 40))

    # Turnover surge detection
    volume_surge = vol_ratio > 2.0

    # Recent volume trend
    vol_5d = df["volume"].tail(5).tolist()
    vol_increasing = all(vol_5d[i] <= vol_5d[i + 1] for i in range(len(vol_5d) - 1))

    return {
        "attention_score": attention_score,
        "volume_ratio": round(float(vol_ratio), 2),
        "volume_surge": bool(volume_surge),
        "vol_increasing": bool(vol_increasing),
        "avg_volume_20d": int(vol_20ma),
        "avg_volume_5d": int(vol_recent),
    }
