"""
Topic researcher — orchestrates multi-source research, scores topics, stores results.

Coordinates Reddit, RSS, Hacker News, and LinkedIn feed data to discover
trending topics and gather rich context for post generation.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta

from backend.research.reddit_scanner import scan_subreddits
from backend.research.rss_scanner import scan_feeds
from backend.research.hn_scanner import scan_top_stories
from backend.research.linkedin_insights import (
    get_trending_from_feed,
    get_high_engagement_posts,
    get_topic_engagement_history,
)
from backend.storage.models import ResearchedTopic, ResearchSnippet
from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)


class TopicResearcher:
    """Orchestrates topic research across multiple sources."""

    def __init__(self, groq_client=None, prompt_loader=None):
        self._groq = groq_client
        self._prompts = prompt_loader

    async def research_topics(self, topics: list[str], db) -> list[dict]:
        """
        Full research pipeline for a list of topics.

        1. Fetch from all enabled sources in parallel
        2. Match snippets to topics
        3. Score each topic via AI
        4. Store results in DB
        5. Clean up expired topics
        6. Return sorted by composite_score

        Args:
            topics: List of topic strings to research.
            db: Database session.

        Returns:
            List of scored topic dicts sorted by composite_score desc.
        """
        logger.info(f"TopicResearcher: starting research for {len(topics)} topics")

        # Step 1: Fetch from all enabled sources in parallel
        all_snippets = await self._fetch_all_sources()
        logger.info(f"TopicResearcher: gathered {len(all_snippets)} total snippets")

        # Step 2: Get LinkedIn feed data (sync DB queries)
        linkedin_trending = get_trending_from_feed(db, days=7)
        linkedin_posts = get_high_engagement_posts(db, min_score=7.0, days=7)

        # Convert LinkedIn data to snippet format
        for lt in linkedin_trending:
            all_snippets.append({
                "title": f"Trending on LinkedIn: {lt['topic']} ({lt['post_count']} posts, avg {lt['avg_likes']} likes)",
                "text": "",
                "url": "",
                "engagement_signal": int(lt["engagement_velocity"]),
                "source": "LINKEDIN",
            })

        for lp in linkedin_posts:
            all_snippets.append({
                "title": f"{lp['author']} on {lp['topic'] or 'LinkedIn'}",
                "text": lp["text_snippet"],
                "url": "",
                "engagement_signal": lp["likes"] + lp["comments"],
                "source": "LINKEDIN",
            })

        # Step 3: Match snippets to topics and score
        results = []
        for topic in topics:
            matched = self._match_snippets_to_topic(topic, all_snippets)
            engagement_history = get_topic_engagement_history(topic, db)

            scores = await self._score_topic(topic, matched, engagement_history)

            # Store in DB
            topic_record = self._store_research(topic, matched, scores, db)
            results.append(topic_record)

        # Step 4: Clean up expired topics
        self._cleanup_expired(db)

        # Sort by composite score
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        logger.info(
            f"TopicResearcher: research complete. "
            f"Top topic: {results[0]['topic']} (score={results[0]['composite_score']:.1f})"
            if results else "TopicResearcher: no topics scored"
        )
        return results

    async def _fetch_all_sources(self) -> list[dict]:
        """Fetch from all enabled sources in parallel."""
        tasks = []

        if cfg_get("research.reddit.enabled", True):
            tasks.append(("reddit", scan_subreddits()))

        if cfg_get("research.rss.enabled", True):
            tasks.append(("rss", scan_feeds()))

        if cfg_get("research.hackernews.enabled", False):
            tasks.append(("hn", scan_top_stories()))

        if not tasks:
            return []

        names, coros = zip(*tasks)
        results = await asyncio.gather(*coros, return_exceptions=True)

        all_snippets = []
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.warning(f"TopicResearcher: {name} source failed — {result}")
                continue
            if isinstance(result, list):
                all_snippets.extend(result)

        return all_snippets

    def _match_snippets_to_topic(
        self, topic: str, snippets: list[dict]
    ) -> list[dict]:
        """Match snippets to a topic via keyword overlap."""
        topic_lower = topic.lower()
        keywords = set(topic_lower.split())
        # Also match on the full topic as a phrase
        matched = []

        for s in snippets:
            text = f"{s.get('title', '')} {s.get('text', '') or s.get('summary', '')}".lower()

            # Check full phrase match
            if topic_lower in text:
                matched.append(s)
                continue

            # Check keyword overlap (at least 50% of topic words must appear)
            if len(keywords) > 0:
                overlap = sum(1 for kw in keywords if kw in text)
                if overlap >= max(1, len(keywords) * 0.5):
                    matched.append(s)

        return matched[:30]  # Cap at 30 snippets per topic

    async def _score_topic(
        self,
        topic: str,
        snippets: list[dict],
        engagement_history: dict,
    ) -> dict:
        """Score a topic using AI (Groq) or fallback heuristics."""
        default_scores = {
            "trending_velocity": 0.0,
            "content_gap": 5.0,
            "relevance": 5.0,
            "suggested_angle": f"Write about {topic} from a practical business perspective",
        }

        if not snippets:
            return default_scores

        # Try AI scoring if groq_client is available
        if self._groq and self._prompts:
            try:
                return await self._ai_score(topic, snippets, engagement_history)
            except Exception as e:
                logger.warning(f"TopicResearcher: AI scoring failed for '{topic}' — {e}")

        # Fallback: heuristic scoring
        return self._heuristic_score(topic, snippets, engagement_history)

    async def _ai_score(
        self,
        topic: str,
        snippets: list[dict],
        engagement_history: dict,
    ) -> dict:
        """Score topic using Groq API with topic_scorer prompt."""
        # Build snippets summary (limit to prevent prompt blowup)
        summary_parts = []
        for s in snippets[:10]:
            title = s.get("title", "")
            text = (s.get("text", "") or s.get("summary", ""))[:200]
            source = s.get("source", "UNKNOWN")
            engagement = s.get("engagement_signal", s.get("upvotes", 0))
            summary_parts.append(
                f"[{source}] {title} (engagement: {engagement})\n{text}"
            )
        snippets_summary = "\n\n".join(summary_parts) or "No relevant discussions found."

        # Format engagement history
        if engagement_history:
            hist_str = (
                f"Posts seen: {engagement_history.get('posts_seen', 0)}, "
                f"Posts engaged: {engagement_history.get('posts_engaged', 0)}, "
                f"Engagement rate: {engagement_history.get('engagement_rate', 0):.1%}, "
                f"Avg score: {engagement_history.get('avg_score', 0):.1f}/10"
            )
        else:
            hist_str = "No historical data available for this topic."

        prompt = self._prompts.format(
            "topic_scorer",
            topic=topic,
            snippet_count=len(snippets),
            snippets_summary=snippets_summary,
            engagement_history=hist_str,
        )

        system = (
            "You are a content strategist. "
            "Return ONLY valid JSON. No preamble, no markdown fences."
        )
        raw = await self._groq.complete(system, prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)
        return {
            "trending_velocity": float(data.get("trending_velocity", 0)),
            "content_gap": float(data.get("content_gap", 5)),
            "relevance": float(data.get("relevance", 5)),
            "suggested_angle": data.get("suggested_angle", f"Write about {topic}"),
        }

    def _heuristic_score(
        self,
        topic: str,
        snippets: list[dict],
        engagement_history: dict,
    ) -> dict:
        """Fallback heuristic scoring when AI is unavailable."""
        # Trending: based on snippet count and engagement signals
        total_engagement = sum(
            s.get("engagement_signal", s.get("upvotes", s.get("score", 0)))
            for s in snippets
        )
        trending = min(10.0, len(snippets) * 0.5 + (total_engagement / 100))

        # Relevance: assume configured topics are relevant
        relevance = 7.0

        # Content gap: inverse of how many snippets (more coverage = less gap)
        content_gap = max(1.0, 8.0 - len(snippets) * 0.3)

        return {
            "trending_velocity": round(trending, 1),
            "content_gap": round(content_gap, 1),
            "relevance": relevance,
            "suggested_angle": f"Write about {topic} from a practical business perspective",
        }

    def _store_research(
        self,
        topic: str,
        snippets: list[dict],
        scores: dict,
        db,
    ) -> dict:
        """Store a ResearchedTopic and its snippets in the DB."""
        weights = {
            "trending": cfg_get("research.scoring_weights.trending", 0.3),
            "engagement": cfg_get("research.scoring_weights.engagement", 0.25),
            "content_gap": cfg_get("research.scoring_weights.content_gap", 0.25),
            "relevance": cfg_get("research.scoring_weights.relevance", 0.2),
        }

        trending_score = scores.get("trending_velocity", 0)
        content_gap_score = scores.get("content_gap", 5)
        relevance_score = scores.get("relevance", 5)

        # Engagement score from snippet engagement signals
        if snippets:
            avg_eng = sum(
                s.get("engagement_signal", s.get("upvotes", s.get("score", 0)))
                for s in snippets
            ) / len(snippets)
            engagement_score = min(10.0, avg_eng / 50)
        else:
            engagement_score = 0.0

        composite = (
            trending_score * weights["trending"]
            + engagement_score * weights["engagement"]
            + content_gap_score * weights["content_gap"]
            + relevance_score * weights["relevance"]
        )

        max_age = cfg_get("research.max_age_hours", 48)
        topic_id = str(uuid.uuid4())

        record = ResearchedTopic(
            id=topic_id,
            topic=topic,
            trending_score=round(trending_score, 1),
            engagement_score=round(engagement_score, 1),
            content_gap_score=round(content_gap_score, 1),
            relevance_score=round(relevance_score, 1),
            composite_score=round(composite, 2),
            suggested_angle=scores.get("suggested_angle", ""),
            snippet_count=len(snippets),
            status="RESEARCHED",
            researched_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=max_age),
        )
        db.add(record)

        # Store snippets
        for s in snippets[:30]:
            snippet_record = ResearchSnippet(
                topic_id=topic_id,
                source=s.get("source", "UNKNOWN"),
                source_url=s.get("url", ""),
                title=(s.get("title", "") or "")[:512],
                snippet=(s.get("text", "") or s.get("summary", ""))[:2000],
                engagement_signal=s.get(
                    "engagement_signal",
                    s.get("upvotes", s.get("score", 0))
                ),
            )
            db.add(snippet_record)

        db.commit()

        return {
            "id": topic_id,
            "topic": topic,
            "trending_score": round(trending_score, 1),
            "engagement_score": round(engagement_score, 1),
            "content_gap_score": round(content_gap_score, 1),
            "relevance_score": round(relevance_score, 1),
            "composite_score": round(composite, 2),
            "suggested_angle": scores.get("suggested_angle", ""),
            "snippet_count": len(snippets),
            "status": "RESEARCHED",
        }

    def _cleanup_expired(self, db) -> int:
        """Delete expired research topics and their snippets."""
        now = datetime.now(timezone.utc)

        expired = (
            db.query(ResearchedTopic)
            .filter(ResearchedTopic.expires_at < now)
            .all()
        )

        count = 0
        for rt in expired:
            db.query(ResearchSnippet).filter_by(topic_id=rt.id).delete()
            db.delete(rt)
            count += 1

        if count:
            db.commit()
            logger.info(f"TopicResearcher: cleaned up {count} expired topics")

        return count


# ── Convenience functions (used by API routes) ──────────────────────────


def get_latest_research(db, limit: int = 20) -> list[dict]:
    """Get most recent non-expired researched topics."""
    now = datetime.now(timezone.utc)

    topics = (
        db.query(ResearchedTopic)
        .filter(
            ResearchedTopic.status != "EXPIRED",
            ResearchedTopic.expires_at > now,
        )
        .order_by(ResearchedTopic.composite_score.desc())
        .limit(limit)
        .all()
    )

    return [_serialize_topic(t) for t in topics]


def get_topic_detail(topic_id: str, db) -> dict | None:
    """Get a single researched topic with all its snippets."""
    topic = db.query(ResearchedTopic).filter_by(id=topic_id).first()
    if not topic:
        return None

    snippets = (
        db.query(ResearchSnippet)
        .filter_by(topic_id=topic_id)
        .order_by(ResearchSnippet.engagement_signal.desc())
        .all()
    )

    result = _serialize_topic(topic)
    result["snippets"] = [
        {
            "id": s.id,
            "source": s.source,
            "source_url": s.source_url,
            "title": s.title,
            "snippet": s.snippet,
            "engagement_signal": s.engagement_signal,
            "discovered_at": s.discovered_at.isoformat() if s.discovered_at else None,
        }
        for s in snippets
    ]
    return result


def get_context_for_generation(topic_id: str, db) -> str:
    """
    Build a formatted context string from snippets for prompt injection.

    Returns a text block summarizing the research findings.
    """
    topic = db.query(ResearchedTopic).filter_by(id=topic_id).first()
    if not topic:
        return ""

    snippets = (
        db.query(ResearchSnippet)
        .filter_by(topic_id=topic_id)
        .order_by(ResearchSnippet.engagement_signal.desc())
        .limit(15)
        .all()
    )

    if not snippets:
        return ""

    parts = []
    for s in snippets:
        source_label = {"REDDIT": "Reddit", "RSS": "Article", "HN": "Hacker News", "LINKEDIN": "LinkedIn"}.get(s.source, s.source)
        title = s.title or "Untitled"
        text = (s.snippet or "")[:300]
        engagement = s.engagement_signal or 0
        parts.append(f"[{source_label}] {title} (engagement: {engagement})\n{text}")

    return "\n\n---\n\n".join(parts)


def mark_used(topic_id: str, db) -> None:
    """Mark a researched topic as USED after generating a post from it."""
    topic = db.query(ResearchedTopic).filter_by(id=topic_id).first()
    if topic:
        topic.status = "USED"
        db.commit()


def _serialize_topic(t: ResearchedTopic) -> dict:
    return {
        "id": t.id,
        "topic": t.topic,
        "trending_score": t.trending_score,
        "engagement_score": t.engagement_score,
        "content_gap_score": t.content_gap_score,
        "relevance_score": t.relevance_score,
        "composite_score": t.composite_score,
        "suggested_angle": t.suggested_angle,
        "snippet_count": t.snippet_count,
        "status": t.status,
        "researched_at": t.researched_at.isoformat() if t.researched_at else None,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
    }
