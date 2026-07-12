"""社群熱度分析 (Social Media & News Buzz Analysis).

Measures discussion volume and sentiment for a stock across:
- PTT Stock board (批踢踢股板)
- Google News (新聞曝光量)
- Volume-based proxy for market attention
"""

import re
import time
import hashlib
import httpx
import pandas as pd
import numpy as np
from datetime import date, timedelta
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

    # Compute composite buzz score (0-100)
    ptt_score = min(100, ptt_result["post_count"] * 5)  # 20 posts = 100
    news_score = min(100, news_result["article_count"] * 10)  # 10 articles = 100
    vol_score = volume_result.get("attention_score", 0)

    buzz_score = int(ptt_score * 0.35 + news_score * 0.35 + vol_score * 0.30)

    # Determine trend
    if ptt_result.get("trend") == "rising" or news_result.get("trend") == "rising":
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
        "fact_check": factcheck_result,
        "volume_attention": volume_result,
        "updated_at": str(date.today()),
    }

    _set_social_cached(cache_key, result)
    return result


async def _scrape_ptt(search_terms: list[str]) -> dict:
    """Scrape PTT Stock board for discussion volume."""
    posts = []
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
                # Extract post titles, links and metadata
                title_pattern = r'<div class="title">\s*<a href="([^"]+)"[^>]*>(.+?)</a>'
                date_pattern = r'<div class="date">\s*(\d+/\d+)'
                push_pattern = r'<span class="hl f\d">(\d+)</span>'

                matches = re.findall(title_pattern, html)
                dates = re.findall(date_pattern, html)
                pushes = re.findall(push_pattern, html)

                for i, (href, title) in enumerate(matches[:20]):
                    post = {
                        "title": title.strip(),
                        "url": f"https://www.ptt.cc{href}" if href.startswith("/") else href,
                        "date": _ptt_date_with_year(dates[i]) if i < len(dates) else "",
                        "push_count": int(pushes[i]) if i < len(pushes) else 0,
                    }
                    posts.append(post)

                    # Simple sentiment from title keywords
                    title_lower = title.lower()
                    if any(w in title_lower for w in ["多", "漲", "噴", "飛", "強", "利多", "看好", "加碼"]):
                        bullish_count += 1
                    elif any(w in title_lower for w in ["空", "跌", "崩", "慘", "利空", "看壞", "減碼", "出"]):
                        bearish_count += 1

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

    # Sentiment
    if bullish_count > bearish_count * 1.5:
        sentiment = "bullish"
    elif bearish_count > bullish_count * 1.5:
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


async def _scrape_news(search_terms: list[str]) -> dict:
    """Scrape Google News for recent news articles."""
    articles = []

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for term in search_terms[:2]:
                # Use Google News RSS
                url = f"https://news.google.com/rss/search?q={term}+stock&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue

                # Parse RSS XML (simplified)
                xml = resp.text
                items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
                for item in items[:10]:
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
