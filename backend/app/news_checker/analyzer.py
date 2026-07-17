"""News credibility analyzer with layered scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field


class NewsCheckRequest(BaseModel):
    url: str
    title: str
    text: str
    published_at: datetime | None = None


class LayerResult(BaseModel):
    layer: str
    score: float = Field(ge=0, le=100)
    weight: float
    detail: str


class NewsCheckResult(BaseModel):
    url: str
    title: str
    source: str
    overall_score: float
    verdict: str
    layers: list[LayerResult]
    summary: str
    published_at: datetime | None = None
    checked_at: datetime


class NewsAnalyzer:
    def __init__(self) -> None:
        self._media_scores = {
            "twse.com.tw": 95,
            "mops.twse.com.tw": 94,
            "cnyes.com": 82,
            "money.udn.com": 80,
            "economicdaily.com.tw": 79,
            "bnext.com.tw": 75,
            "ctee.com.tw": 74,
            "ptt.cc": 40,
            "dcard.tw": 35,
        }
        self._trusted_sources = {
            "twse.com.tw",
            "mops.twse.com.tw",
            "cnyes.com",
            "money.udn.com",
            "economicdaily.com.tw",
        }

    async def analyze(self, payload: NewsCheckRequest) -> NewsCheckResult:
        domain = self._extract_domain(payload.url)
        layers = [
            self._media_layer(domain),
            await self._cofacts_layer(payload),
            self._content_layer(payload),
            self._cross_validation_layer(payload, domain),
            self._timeliness_layer(payload.published_at),
        ]
        overall_score = round(sum(layer.score * layer.weight for layer in layers), 2)
        verdict = self._verdict(overall_score)
        summary = self._summary(verdict, domain, layers)
        result = NewsCheckResult(
            url=payload.url,
            title=payload.title,
            source=domain,
            overall_score=overall_score,
            verdict=verdict,
            layers=layers,
            summary=summary,
            published_at=payload.published_at,
            checked_at=datetime.utcnow(),
        )
        await self._persist(result)
        return result

    async def _persist(self, result: NewsCheckResult) -> None:
        """S3：檢查紀錄存進 Mongo，不再只留在 process 記憶體（重啟就消失，
        多 worker 時各自看到不同歷史）。best-effort，存檔失敗不影響這次
        檢查本身已經算出的結果。"""
        try:
            from ..db.mongodb import get_mongodb

            db = await get_mongodb()
            await db.news_checks.insert_one(result.model_dump(mode="json"))
            # 只保留最近 200 筆，避免集合無限成長
            count = await db.news_checks.count_documents({})
            if count > 200:
                stale = db.news_checks.find({}, {"_id": 1}).sort("checked_at", 1).limit(count - 200)
                stale_ids = [doc["_id"] async for doc in stale]
                if stale_ids:
                    await db.news_checks.delete_many({"_id": {"$in": stale_ids}})
        except Exception:
            pass

    async def get_crawled_data(self, source: str | None = None, limit: int = 50) -> list[NewsCheckResult]:
        try:
            from ..db.mongodb import get_mongodb

            db = await get_mongodb()
            query = {"source": {"$regex": source, "$options": "i"}} if source else {}
            cursor = db.news_checks.find(query).sort("checked_at", -1).limit(limit)
            items = []
            async for doc in cursor:
                doc.pop("_id", None)
                try:
                    items.append(NewsCheckResult(**doc))
                except Exception:
                    continue
            return items
        except Exception:
            return []

    def _media_layer(self, domain: str) -> LayerResult:
        score = float(self._media_scores.get(domain, 55))
        detail = f"Source {domain} credibility baseline: {score:.0f}/100."
        return LayerResult(layer="media_source", score=score, weight=0.30, detail=detail)

    async def _cofacts_layer(self, payload: NewsCheckRequest) -> LayerResult:
        excerpt = f"{payload.title} {payload.text}".strip()[:180]
        if not excerpt:
            return LayerResult(
                layer="cofacts",
                score=50,
                weight=0.25,
                detail="No text available for Cofacts verification.",
            )

        query = """
        query($text: String!) {
          ListArticles(filter: {moreLikeThis: $text}, first: 3) {
            edges {
              node {
                text
                articleReplies {
                  reply {
                    type
                    text
                  }
                }
              }
            }
          }
        }
        """
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                response = await client.post(
                    "https://api.cofacts.tw/graphql",
                    json={"query": query, "variables": {"text": excerpt}},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            return LayerResult(
                layer="cofacts",
                score=50,
                weight=0.25,
                detail=f"Cofacts lookup unavailable: {exc}",
            )

        edges = (
            data.get("data", {})
            .get("ListArticles", {})
            .get("edges", [])
        )
        if not edges:
            return LayerResult(
                layer="cofacts",
                score=60,
                weight=0.25,
                detail="No matching Cofacts article found.",
            )

        reply_types = []
        for edge in edges:
            replies = edge.get("node", {}).get("articleReplies", [])
            for reply in replies:
                reply_type = reply.get("reply", {}).get("type")
                if reply_type:
                    reply_types.append(reply_type)

        if any(reply_type == "RUMOR" for reply_type in reply_types):
            score = 25
            detail = "Cofacts found rumor-classified replies."
        elif any(reply_type == "NOT_RUMOR" for reply_type in reply_types):
            score = 88
            detail = "Cofacts found non-rumor corroboration."
        else:
            score = 58
            detail = "Cofacts returned related discussion without decisive classification."

        return LayerResult(layer="cofacts", score=score, weight=0.25, detail=detail)

    def _content_layer(self, payload: NewsCheckRequest) -> LayerResult:
        text = f"{payload.title} {payload.text}".lower()
        suspicious_keywords = ["內幕", "保證獲利", "翻倍", "明牌", "絕對", "飆股", "獨家爆料", "匿名消息"]
        quality_keywords = ["財報", "公開資訊觀測站", "證交所", "法說會", "公告", "來源", "數據"]
        suspicious_hits = sum(1 for keyword in suspicious_keywords if keyword.lower() in text)
        quality_hits = sum(1 for keyword in quality_keywords if keyword.lower() in text)
        score = max(5, min(95, 60 - suspicious_hits * 12 + quality_hits * 8))
        detail = f"Suspicious keywords={suspicious_hits}, quality keywords={quality_hits}."
        return LayerResult(layer="content_quality", score=score, weight=0.20, detail=detail)

    def _cross_validation_layer(self, payload: NewsCheckRequest, domain: str) -> LayerResult:
        text = f"{payload.title} {payload.text}".lower()
        trusted_mentions = sum(1 for source in self._trusted_sources if source.lower() in text)
        official_mentions = sum(
            1 for token in ["證交所", "金管會", "公開資訊觀測站", "mops", "twse"] if token.lower() in text
        )
        score = 45
        if domain in self._trusted_sources:
            score += 15
        score += min(25, trusted_mentions * 10 + official_mentions * 7)
        score = min(95, score)
        detail = f"Trusted mentions={trusted_mentions}, official references={official_mentions}."
        return LayerResult(layer="cross_validation", score=score, weight=0.15, detail=detail)

    def _timeliness_layer(self, published_at: datetime | None) -> LayerResult:
        if published_at is None:
            return LayerResult(
                layer="timeliness",
                score=55,
                weight=0.10,
                detail="Published time missing; assigned neutral freshness score.",
            )
        published = published_at.astimezone(timezone.utc) if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
        if age_hours <= 6:
            score = 95
        elif age_hours <= 24:
            score = 85
        elif age_hours <= 72:
            score = 72
        elif age_hours <= 168:
            score = 60
        else:
            score = 45
        return LayerResult(
            layer="timeliness",
            score=score,
            weight=0.10,
            detail=f"Published {age_hours:.1f} hours ago.",
        )

    @staticmethod
    def _extract_domain(url: str) -> str:
        hostname = urlparse(url).hostname or ""
        return hostname.lower().removeprefix("www.")

    @staticmethod
    def _verdict(score: float) -> str:
        if score >= 75:
            return "CREDIBLE"
        if score >= 50:
            return "UNCERTAIN"
        return "SUSPICIOUS"

    @staticmethod
    def _summary(verdict: str, domain: str, layers: list[LayerResult]) -> str:
        weakest = min(layers, key=lambda item: item.score)
        strongest = max(layers, key=lambda item: item.score)
        return (
            f"{domain or 'Unknown source'} is rated {verdict}. "
            f"Strongest layer: {strongest.layer} ({strongest.score:.0f}). "
            f"Weakest layer: {weakest.layer} ({weakest.score:.0f})."
        )


news_analyzer = NewsAnalyzer()
