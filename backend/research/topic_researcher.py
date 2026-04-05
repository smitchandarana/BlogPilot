"""
Topic researcher — orchestrates multi-source research, scores topics, stores results.

Coordinates Reddit, RSS, Hacker News, and LinkedIn feed data to discover
trending subtopics and gather rich context for post generation.

Pipeline:
  Fetch snippets → Domain-filter → AI extract subtopics → Score → Quality gate → Store
"""
import asyncio
import json
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta

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

# Stopwords for heuristic extraction
_STOPWORDS = frozenset(
    "the a an and or but in on at to for of is it this that with from by as are was "
    "were be been being have has had do does did will would could should may might can "
    "shall not no so if than too very just about also how what when where who which why "
    "all each every both few more most other some such any into over after before between "
    "through during without within along across above below up down out off on upon "
    "i me my we our you your he she they them their its his her".split()
)


class TopicResearcher:
    """Orchestrates topic research across multiple sources."""

    def __init__(self, groq_client=None, prompt_loader=None):
        self._groq = groq_client
        self._prompts = prompt_loader

    async def research_topics(self, topics: list[str], db) -> list[dict]:
        """
        Full research pipeline for a list of broad domain topics.

        1. Fetch from all enabled sources in parallel
        2. Domain-filter snippets per broad topic
        3. AI-extract specific subtopics from filtered snippets
        4. Deduplicate subtopics across domains
        5. Score each subtopic
        6. Quality gate — drop low-scoring subtopics
        7. Store results in DB
        8. Clean up expired topics
        9. Return sorted by composite_score
        """
        logger.info(f"TopicResearcher: starting research for {len(topics)} domains")

        # Step 1: Fetch from all enabled sources in parallel
        all_snippets = await self._fetch_all_sources()
        logger.info(f"TopicResearcher: gathered {len(all_snippets)} total snippets")

        # Step 2: Get LinkedIn feed data (sync DB queries)
        linkedin_trending = get_trending_from_feed(db, days=7)
        linkedin_posts = get_high_engagement_posts(db, min_score=7.0, days=7)

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

        # Step 3: Domain-filter snippets, then extract subtopics
        max_per_domain = int(cfg_get("research.max_subtopics_per_domain", 5))
        max_total = int(cfg_get("research.max_total_subtopics", 20))
        all_subtopics = []

        for domain in topics:
            domain_snippets = self._match_snippets_to_domain(domain, all_snippets)
            if not domain_snippets:
                logger.info(f"TopicResearcher: no snippets matched domain '{domain}', skipping")
                continue

            extracted = await self._extract_subtopics(domain, domain_snippets)
            # Cap per domain
            all_subtopics.extend(extracted[:max_per_domain])

        # Step 4: Deduplicate across domains
        unique_subtopics = self._deduplicate_subtopics(all_subtopics)
        # Cap total
        unique_subtopics = unique_subtopics[:max_total]

        logger.info(f"TopicResearcher: extracted {len(unique_subtopics)} unique subtopics")

        # Step 5: Score each subtopic concurrently + quality gate
        min_score = float(cfg_get("research.min_subtopic_score", 4.0))
        results = []

        # Limit concurrent Groq calls to avoid TPM rate limits on free tier
        _sem = asyncio.Semaphore(3)

        async def _score_one(item):
            async with _sem:
                engagement_history = get_topic_engagement_history(item["subtopic"], db)
                scores = await self._score_topic(item["subtopic"], item["supporting_snippets"], engagement_history)
                composite = self._compute_composite(scores, item["supporting_snippets"])
                return item, scores, composite

        scored = await asyncio.gather(*[_score_one(it) for it in unique_subtopics])

        for item, scores, composite in scored:
            if composite < min_score:
                logger.info(
                    f"TopicResearcher: dropped subtopic '{item['subtopic']}' — "
                    f"score {composite:.1f} below threshold {min_score}"
                )
                continue

            record = self._store_research(
                item["subtopic"], item["supporting_snippets"], scores, db,
                domain=item["domain"],
            )
            results.append(record)

        # Step 6: Clean up expired topics
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

    def _match_snippets_to_domain(
        self, domain: str, snippets: list[dict]
    ) -> list[dict]:
        """Match snippets to a broad domain via keyword overlap."""
        domain_lower = domain.lower()
        keywords = set(domain_lower.split())
        matched = []

        for s in snippets:
            text = f"{s.get('title', '')} {s.get('text', '') or s.get('summary', '')}".lower()

            # Check full phrase match
            if domain_lower in text:
                matched.append(s)
                continue

            # Check keyword overlap (at least 50% of domain words must appear)
            if len(keywords) > 0:
                overlap = sum(1 for kw in keywords if kw in text)
                if overlap >= max(1, len(keywords) * 0.5):
                    matched.append(s)

        return matched[:30]  # Cap at 30 snippets per domain

    async def _extract_subtopics(
        self, domain: str, snippets: list[dict]
    ) -> list[dict]:
        """
        Extract specific subtopics from snippets using AI or heuristic fallback.

        Returns list of {subtopic: str, domain: str, supporting_snippets: list[dict]}.
        """
        if self._groq and self._prompts:
            try:
                return await self._ai_extract_subtopics(domain, snippets)
            except Exception as e:
                logger.warning(f"TopicResearcher: AI extraction failed for '{domain}' — {e}")

        return self._heuristic_extract_subtopics(domain, snippets)

    async def _ai_extract_subtopics(
        self, domain: str, snippets: list[dict]
    ) -> list[dict]:
        """Use Groq to extract specific subtopics from snippet content."""
        # Sort by engagement and take top 15
        sorted_snippets = sorted(
            snippets,
            key=lambda s: s.get("engagement_signal", s.get("upvotes", 0)),
            reverse=True,
        )[:15]

        summary_parts = []
        for s in sorted_snippets:
            title = s.get("title", "")
            text = (s.get("text", "") or s.get("summary", ""))[:200]
            source = s.get("source", "UNKNOWN")
            engagement = s.get("engagement_signal", s.get("upvotes", 0))
            summary_parts.append(
                f"[{source}] {title} (engagement: {engagement})\n{text}"
            )
        snippets_summary = "\n\n".join(summary_parts) or "No discussions found."

        prompt = self._prompts.format(
            "topic_extractor",
            domain=domain,
            snippet_count=len(sorted_snippets),
            snippets_summary=snippets_summary,
        )

        system = (
            "You are a content research assistant. "
            "Return ONLY valid JSON. No preamble, no markdown fences."
        )
        raw = await self._groq.complete(system, prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(
                f"TopicResearcher: JSON parse failed in _ai_extract_subtopics for '{domain}' — {e}"
            )
            return self._heuristic_extract_subtopics(domain, snippets)

        extracted_topics = data.get("specific_topics", [])

        # Filter out any that exactly match the domain name
        domain_lower = domain.lower().strip()
        extracted_topics = [
            t for t in extracted_topics
            if t.lower().strip() != domain_lower
        ]

        logger.info(
            f"TopicResearcher: AI extracted {len(extracted_topics)} subtopics "
            f"from domain '{domain}'"
        )

        # Map each subtopic back to supporting snippets
        result = []
        for subtopic in extracted_topics:
            supporting = self._find_supporting_snippets(subtopic, snippets)
            result.append({
                "subtopic": subtopic,
                "domain": domain,
                "supporting_snippets": supporting,
            })

        return result

    def _heuristic_extract_subtopics(
        self, domain: str, snippets: list[dict]
    ) -> list[dict]:
        """Fallback: extract subtopics using n-gram frequency from snippet titles."""
        domain_words = set(domain.lower().split())

        # Collect all title words
        all_titles = []
        for s in snippets:
            title = s.get("title", "") or ""
            all_titles.append(title)

        # Extract bigrams and trigrams from titles
        ngram_counts = Counter()
        for title in all_titles:
            words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", title.lower())
            # Filter stopwords and domain words
            words = [w for w in words if w not in _STOPWORDS and w not in domain_words and len(w) > 2]

            # Bigrams
            for i in range(len(words) - 1):
                ngram = f"{words[i]} {words[i+1]}"
                ngram_counts[ngram] += 1

            # Trigrams
            for i in range(len(words) - 2):
                ngram = f"{words[i]} {words[i+1]} {words[i+2]}"
                ngram_counts[ngram] += 1

        # Take top phrases that appear in at least 2 snippets
        top_phrases = [
            phrase for phrase, count in ngram_counts.most_common(15)
            if count >= 2
        ][:5]

        # If we didn't get enough, also use single significant words
        if len(top_phrases) < 3:
            word_counts = Counter()
            for title in all_titles:
                words = re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", title.lower())
                for w in words:
                    if w not in _STOPWORDS and w not in domain_words and len(w) > 3:
                        word_counts[w] += 1
            for word, count in word_counts.most_common(10):
                if count >= 2 and word not in " ".join(top_phrases):
                    top_phrases.append(word)
                    if len(top_phrases) >= 5:
                        break

        # Title-case and build result
        result = []
        for phrase in top_phrases:
            subtopic = phrase.title()
            supporting = self._find_supporting_snippets(subtopic, snippets)
            result.append({
                "subtopic": subtopic,
                "domain": domain,
                "supporting_snippets": supporting,
            })

        logger.info(
            f"TopicResearcher: heuristic extracted {len(result)} subtopics "
            f"from domain '{domain}'"
        )
        return result

    def _find_supporting_snippets(
        self, subtopic: str, snippets: list[dict]
    ) -> list[dict]:
        """Find snippets that support a specific subtopic via keyword match."""
        subtopic_lower = subtopic.lower()
        keywords = set(
            w for w in re.findall(r"[a-zA-Z]+(?:'[a-zA-Z]+)?", subtopic_lower)
            if w not in _STOPWORDS and len(w) > 2
        )

        supporting = []
        for s in snippets:
            text = f"{s.get('title', '')} {s.get('text', '') or s.get('summary', '')}".lower()

            # Full phrase match
            if subtopic_lower in text:
                supporting.append(s)
                continue

            # Keyword overlap — at least 50% of subtopic words
            if keywords:
                overlap = sum(1 for kw in keywords if kw in text)
                if overlap >= max(1, len(keywords) * 0.5):
                    supporting.append(s)

        return supporting[:15]

    def _deduplicate_subtopics(self, subtopics: list[dict]) -> list[dict]:
        """Deduplicate subtopics: merge exact dupes, collapse substring matches."""
        if not subtopics:
            return []

        # Normalize and group
        seen = {}  # normalized_name -> item
        for item in subtopics:
            key = item["subtopic"].lower().strip()
            if key in seen:
                # Merge: keep the one with more supporting snippets
                existing = seen[key]
                if len(item["supporting_snippets"]) > len(existing["supporting_snippets"]):
                    seen[key] = item
            else:
                seen[key] = item

        # Collapse substring matches (keep the longer/more specific one)
        keys = list(seen.keys())
        to_remove = set()
        for i, k1 in enumerate(keys):
            if k1 in to_remove:
                continue
            for k2 in keys[i + 1:]:
                if k2 in to_remove:
                    continue
                if k1 in k2:
                    # k1 is substring of k2 — remove shorter k1
                    to_remove.add(k1)
                    break
                elif k2 in k1:
                    # k2 is substring of k1 — remove shorter k2
                    to_remove.add(k2)

        return [seen[k] for k in keys if k not in to_remove]

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

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(
                f"TopicResearcher: JSON parse failed in _ai_score for '{topic}' — {e}"
            )
            return self._heuristic_score(topic, snippets, engagement_history)

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
        total_engagement = sum(
            s.get("engagement_signal", s.get("upvotes", s.get("score", 0)))
            for s in snippets
        )
        trending = min(10.0, len(snippets) * 0.5 + (total_engagement / 100))
        relevance = 7.0
        content_gap = max(1.0, 8.0 - len(snippets) * 0.3)

        return {
            "trending_velocity": round(trending, 1),
            "content_gap": round(content_gap, 1),
            "relevance": relevance,
            "suggested_angle": f"Write about {topic} from a practical business perspective",
        }

    def _compute_composite(self, scores: dict, snippets: list[dict]) -> float:
        """Compute weighted composite score for quality gate check."""
        weights = {
            "trending": cfg_get("research.scoring_weights.trending", 0.3),
            "engagement": cfg_get("research.scoring_weights.engagement", 0.25),
            "content_gap": cfg_get("research.scoring_weights.content_gap", 0.25),
            "relevance": cfg_get("research.scoring_weights.relevance", 0.2),
        }

        trending_score = scores.get("trending_velocity", 0)
        content_gap_score = scores.get("content_gap", 5)
        relevance_score = scores.get("relevance", 5)

        if snippets:
            avg_eng = sum(
                s.get("engagement_signal", s.get("upvotes", s.get("score", 0)))
                for s in snippets
            ) / len(snippets)
            engagement_score = min(10.0, avg_eng / 50)
        else:
            engagement_score = 0.0

        return (
            trending_score * weights["trending"]
            + engagement_score * weights["engagement"]
            + content_gap_score * weights["content_gap"]
            + relevance_score * weights["relevance"]
        )

    def _store_research(
        self,
        topic: str,
        snippets: list[dict],
        scores: dict,
        db,
        domain: str = None,
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
            domain=domain,
            trending_score=round(trending_score, 1),
            engagement_score=round(engagement_score, 1),
            content_gap_score=round(content_gap_score, 1),
            relevance_score=round(relevance_score, 1),
            composite_score=round(composite, 2),
            suggested_angle=scores.get("suggested_angle", ""),
            snippet_count=len(snippets),
            status="RESEARCHED",
            researched_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=max_age),
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
            "domain": domain,
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
        now = datetime.utcnow()

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
    now = datetime.utcnow()

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


def clear_all_topics(db) -> int:
    """Delete all researched topics and their snippets."""
    topic_ids = [t.id for t in db.query(ResearchedTopic.id).all()]
    if not topic_ids:
        return 0

    db.query(ResearchSnippet).filter(
        ResearchSnippet.topic_id.in_(topic_ids)
    ).delete(synchronize_session=False)
    count = db.query(ResearchedTopic).delete(synchronize_session=False)
    db.commit()

    logger.info(f"TopicResearcher: cleared all {count} researched topics")
    return count


def _serialize_topic(t: ResearchedTopic) -> dict:
    return {
        "id": t.id,
        "topic": t.topic,
        "domain": t.domain,
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
