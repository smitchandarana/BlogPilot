"""
Content Extractor — structured insight extraction from research snippets.

Processes raw research_snippets through an LLM to extract:
  topic, subtopic, pain_point, hook_type, content_style,
  key_insight, audience_segment, sentiment, specificity_score

Usage:
    extractor = ContentExtractor(groq_client, prompt_loader)
    insights = await extractor.extract_from_snippets(db, batch_size=20)
"""
import asyncio
import json
from datetime import datetime, timezone

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_SYSTEM = (
    "You are a content intelligence analyst. "
    "Return ONLY valid JSON. No preamble, no markdown fences."
)

_VALID_HOOK_TYPES = {"CONTRARIAN", "QUESTION", "STAT", "STORY", "TREND", "MISTAKE"}
_VALID_STYLES = {"TACTICAL", "STRATEGIC", "PERSONAL", "EDUCATIONAL", "PROVOCATIVE"}
_VALID_SENTIMENTS = {"POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"}


class ContentExtractor:
    """
    Extracts structured insights from research snippets using AI.

    One snippet → one ContentInsight row (or zero if extraction/quality gate fails).
    Uses a semaphore to limit concurrent Groq calls.
    """

    def __init__(self, groq_client=None, prompt_loader=None):
        self._groq = groq_client
        self._prompts = prompt_loader

    # ── Public API ────────────────────────────────────────────────────────

    async def extract_from_snippets(self, db, batch_size: int = 20) -> list[dict]:
        """
        Process unprocessed research snippets → structured insights → store in DB.

        Args:
            db:         SQLAlchemy session.
            batch_size: Max snippets to process in one call.

        Returns:
            List of created insight dicts.
        """
        if self._groq is None or self._prompts is None:
            logger.warning("ContentExtractor: no Groq client — skipping extraction")
            return []

        from backend.storage.models import ResearchSnippet, ResearchedTopic, ContentInsight

        # Query unprocessed snippets
        try:
            rows = (
                db.query(ResearchSnippet)
                .filter(ResearchSnippet.processed_for_insights == False)  # noqa: E712
                .order_by(ResearchSnippet.engagement_signal.desc())
                .limit(batch_size)
                .all()
            )
        except Exception as e:
            logger.error(f"ContentExtractor: DB query failed — {e}")
            return []

        if not rows:
            logger.info("ContentExtractor: no unprocessed snippets found")
            return []

        logger.info(f"ContentExtractor: processing {len(rows)} snippets")

        # Build topic lookup (snippet_id → domain)
        topic_ids = {r.topic_id for r in rows}
        topic_map = {}
        try:
            topics = db.query(ResearchedTopic).filter(
                ResearchedTopic.id.in_(topic_ids)
            ).all()
            topic_map = {t.id: t for t in topics}
        except Exception:
            pass

        # Limit concurrency to avoid Groq rate limits
        semaphore = asyncio.Semaphore(2)
        min_score = float(cfg_get("content_intelligence.min_specificity_score", 3.0))

        created = []

        async def _process_one(snippet):
            async with semaphore:
                topic = topic_map.get(snippet.topic_id)
                domain = topic.domain or topic.topic if topic else ""
                try:
                    data = await self._extract_single(snippet, domain)
                except Exception as e:
                    logger.warning(f"ContentExtractor: snippet {snippet.id} failed — {e}")
                    data = None

                try:
                    # Mark processed regardless of success
                    snippet.processed_for_insights = True
                    db.commit()
                except Exception:
                    pass

                if data is None:
                    return None

                # Quality gate
                if float(data.get("specificity_score", 0)) < min_score:
                    logger.debug(
                        f"ContentExtractor: snippet {snippet.id} dropped — "
                        f"specificity {data.get('specificity_score')} < {min_score}"
                    )
                    return None

                # Store insight
                try:
                    insight = ContentInsight(
                        snippet_id=snippet.id,
                        topic=topic.topic if topic else "",
                        subtopic=data.get("subtopic", ""),
                        pain_point=data.get("pain_point", ""),
                        hook_type=data.get("hook_type", ""),
                        content_style=data.get("content_style", ""),
                        key_insight=data.get("key_insight", ""),
                        audience_segment=data.get("audience_segment", ""),
                        sentiment=data.get("sentiment", "NEUTRAL"),
                        specificity_score=float(data.get("specificity_score", 0)),
                        source_engagement=snippet.engagement_signal or 0,
                        source_type=snippet.source,
                    )
                    db.add(insight)
                    db.commit()
                    db.refresh(insight)
                    logger.info(
                        f"ContentExtractor: insight created — "
                        f"subtopic='{insight.subtopic}' hook={insight.hook_type} "
                        f"score={insight.specificity_score}"
                    )
                    return {
                        "id": insight.id,
                        "subtopic": insight.subtopic,
                        "pain_point": insight.pain_point,
                        "hook_type": insight.hook_type,
                        "content_style": insight.content_style,
                        "key_insight": insight.key_insight,
                        "audience_segment": insight.audience_segment,
                        "specificity_score": insight.specificity_score,
                        "source_type": insight.source_type,
                    }
                except Exception as e:
                    logger.error(f"ContentExtractor: failed to store insight — {e}")
                    return None

        results = await asyncio.gather(*[_process_one(s) for s in rows])
        created = [r for r in results if r is not None]
        logger.info(f"ContentExtractor: created {len(created)} insights from {len(rows)} snippets")
        return created

    async def extract_from_raw_text(self, text: str, source: str = "MANUAL", db=None) -> dict | None:
        """
        Extract a structured insight from manually pasted text.
        Does NOT require a snippet_id — useful for Phase B manual ingestion.

        Returns the created ContentInsight dict or None on failure.
        """
        if self._groq is None or self._prompts is None:
            logger.warning("ContentExtractor: no Groq client")
            return None

        from backend.storage.models import ContentInsight

        data = await self._extract_single_text(
            title="Manual input",
            content=text[:3000],
            source_type=source,
            domain="",
        )
        if data is None:
            return None

        min_score = float(cfg_get("content_intelligence.min_specificity_score", 3.0))
        if float(data.get("specificity_score", 0)) < min_score:
            return None

        if db is None:
            return data

        try:
            insight = ContentInsight(
                snippet_id=None,
                topic=data.get("subtopic", ""),
                subtopic=data.get("subtopic", ""),
                pain_point=data.get("pain_point", ""),
                hook_type=data.get("hook_type", ""),
                content_style=data.get("content_style", ""),
                key_insight=data.get("key_insight", ""),
                audience_segment=data.get("audience_segment", ""),
                sentiment=data.get("sentiment", "NEUTRAL"),
                specificity_score=float(data.get("specificity_score", 0)),
                source_engagement=0,
                source_type=source,
            )
            db.add(insight)
            db.commit()
            db.refresh(insight)
            return {
                "id": insight.id,
                "subtopic": insight.subtopic,
                "pain_point": insight.pain_point,
                "hook_type": insight.hook_type,
                "content_style": insight.content_style,
                "key_insight": insight.key_insight,
                "audience_segment": insight.audience_segment,
                "specificity_score": insight.specificity_score,
                "source_type": insight.source_type,
            }
        except Exception as e:
            logger.error(f"ContentExtractor: failed to store manual insight — {e}")
            return None

    # ── Private helpers ───────────────────────────────────────────────────

    async def _extract_single(self, snippet, domain: str = "") -> dict | None:
        """Extract structured insight from a ResearchSnippet row."""
        content = (snippet.snippet or snippet.title or "")[:2000]
        title = snippet.title or ""
        return await self._extract_single_text(
            title=title,
            content=content,
            source_type=snippet.source,
            domain=domain,
        )

    async def _extract_single_text(
        self,
        title: str,
        content: str,
        source_type: str,
        domain: str,
    ) -> dict | None:
        """Core extraction: format prompt, call Groq, parse JSON."""
        try:
            prompt = self._prompts.format(
                "content_extractor",
                source_type=source_type,
                title=title,
                content=content,
                domain=domain or "Business Analytics & Reporting",
            )
        except Exception as e:
            logger.warning(f"ContentExtractor: prompt format failed — {e}")
            return None

        try:
            raw = await self._groq.complete(_SYSTEM, prompt)
            raw = raw.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract first JSON object
            import re
            m = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                except Exception:
                    logger.warning(f"ContentExtractor: JSON parse failed after regex fallback")
                    return None
            else:
                logger.warning(f"ContentExtractor: no JSON found in response")
                return None
        except Exception as e:
            logger.warning(f"ContentExtractor: Groq call failed — {e}")
            return None

        # Normalize and validate
        hook = str(data.get("hook_type", "")).upper()
        if hook not in _VALID_HOOK_TYPES:
            hook = "STORY"
        style = str(data.get("content_style", "")).upper()
        if style not in _VALID_STYLES:
            style = "EDUCATIONAL"
        sentiment = str(data.get("sentiment", "")).upper()
        if sentiment not in _VALID_SENTIMENTS:
            sentiment = "NEUTRAL"

        try:
            score = float(data.get("specificity_score", 0))
            score = max(0.0, min(10.0, score))
        except (TypeError, ValueError):
            score = 0.0

        return {
            "subtopic": str(data.get("subtopic", ""))[:256],
            "pain_point": str(data.get("pain_point", ""))[:512],
            "hook_type": hook,
            "content_style": style,
            "key_insight": str(data.get("key_insight", "")),
            "audience_segment": str(data.get("audience_segment", ""))[:128],
            "sentiment": sentiment,
            "specificity_score": score,
        }
