"""PP4：上網搜尋工具（DuckDuckGo Instant Answers + SSRF 防護的網頁抓取）。

設計原則：
- 不需要 API key（DuckDuckGo JSON 端點免費公開）。
- 網頁抓取重用 imports.py 的 SSRF 防護邏輯，確保不被用來探測內網。
- 函式都是同步（用 requests），由 ask.py 在 asyncio.to_thread 裡呼叫。
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import requests
import trafilatura

logger = logging.getLogger(__name__)

_DDG_API = "https://api.duckduckgo.com/"
_WEB_FETCH_MAX_CHARS = 3000
_REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; KbWeb/1.0)"}


# ── SSRF 防護（複製自 imports.py，獨立維護以避免跨模組耦合）──────────────────
def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("只允許 http/https 網址。")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("網址格式不正確。")
    try:
        resolved = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError(f"無法解析主機：{hostname}") from exc
    for ip_str in resolved:
        ip = ipaddress.ip_address(ip_str)
        if any([ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_reserved, ip.is_multicast]):
            raise ValueError(f"不允許存取內網/本機位址（{ip_str}）。")


# ── 公開介面 ──────────────────────────────────────────────────────────────────

def web_search(query: str) -> str:
    """DuckDuckGo Instant Answer API。回傳格式化文字，適合塞進 prompt。"""
    try:
        resp = requests.get(
            _DDG_API,
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=12,
            headers=_REQUEST_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("web_search DDG request failed: %s", exc)
        return f"（搜尋失敗：{exc}）"

    parts: list[str] = []
    if data.get("Answer"):
        parts.append(f"**直接答案**：{data['Answer']}")
    if data.get("Abstract"):
        src = data.get("AbstractSource") or data.get("AbstractURL", "")
        parts.append(f"**摘要**（{src}）：{data['Abstract']}")
    for topic in (data.get("RelatedTopics") or [])[:4]:
        if isinstance(topic, dict) and topic.get("Text"):
            url = topic.get("FirstURL", "")
            line = f"- {topic['Text']}"
            if url:
                line += f"\n  來源：{url}"
            parts.append(line)
    for result in (data.get("Results") or [])[:3]:
        if isinstance(result, dict) and result.get("Text"):
            url = result.get("FirstURL", "")
            line = f"- {result['Text']}"
            if url:
                line += f"\n  來源：{url}"
            parts.append(line)

    if not parts:
        return "（DuckDuckGo 未找到相關結果，請嘗試其他關鍵字）"
    return "\n\n".join(parts)


def fetch_url(url: str) -> str:
    """抓取並擷取網頁正文（SSRF 防護）。最多回傳 3000 字。"""
    try:
        _assert_public_url(url)
    except ValueError as exc:
        return f"（無法存取該網址：{exc}）"

    try:
        resp = requests.get(url, timeout=15, headers=_REQUEST_HEADERS)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("fetch_url failed for %s: %s", url, exc)
        return f"（抓取失敗：{exc}）"

    extracted = trafilatura.extract(resp.text, include_comments=False, favor_recall=True)
    if not extracted or len(extracted.strip()) < 50:
        return "（無法從該頁面擷取有意義的內文，可能是動態渲染的網站）"

    text = extracted[:_WEB_FETCH_MAX_CHARS]
    if len(extracted) > _WEB_FETCH_MAX_CHARS:
        text += "\n…（已截斷）"
    return text
