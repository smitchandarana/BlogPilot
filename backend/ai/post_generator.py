"""
Post generator — creates an original LinkedIn post on a given topic.

Sprint 10: Enhanced with quality gate scoring before publishing.

Usage:
    result = await generate(topic, style, tone, word_count, groq_client, prompt_loader)
    # result is a dict: {"post": str, "quality_score": float, "approved": bool, ...}
"""
import json

from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.ai.utils import parse_json_safe
from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_SYSTEM = (
    "You are a LinkedIn content strategist. "
    "Write only the post text — no title, no intro, no explanation."
)

_SYSTEM_STRUCTURED = (
    "You are a world-class LinkedIn ghostwriter specializing in B2B analytics and data strategy. "
    "You write posts that stop the scroll, make one sharp argument, and sound like a real expert — not a content bot. "
    "Write ONLY the post text. No title. No 'Here is your post:'. No explanation after the post."
)

_SYSTEM_SCORER = (
    "You are a post quality evaluator. "
    "Return ONLY valid JSON. No preamble, no markdown fences."
)

_HOOK_INSTRUCTIONS = {
    "CONTRARIAN": (
        "Open by quoting or paraphrasing the conventional wisdom you are about to destroy — "
        "attribute it to 'most BI teams', 'the standard playbook', or 'what every consultant recommends'. "
        "Then in the same paragraph, deliver the contradiction with one concrete specific. "
        "Do NOT use: 'But here's the thing:', 'Think again:', 'Wrong.', or 'Not so fast.'"
    ),
    "QUESTION": (
        "Open with a question your exact audience is already asking in private — "
        "something they'd say in a hallway, not a keynote. "
        "It must be answerable, not rhetorical. Frame it around a specific decision or scenario. "
        "Do NOT use: 'Have you ever...', 'What if...', 'Why does...', or any question about 'the future'."
    ),
    "STAT": (
        "CRITICAL: Only use a statistic that was explicitly provided in the Core Insight field. "
        "If no real statistic was provided, DO NOT invent one — not even a plausible-sounding one. "
        "Instead, switch to a STORY hook: drop into a specific moment where someone discovers the problem. "
        "Fabricated statistics destroy credibility when readers research them."
    ),
    "STORY": (
        "Start in the middle of a specific moment — not backstory, not context-setting. "
        "Name a specific role: 'The CFO', 'the analyst who built the model', 'the ops director'. "
        "First sentence should create a scene the audience recognizes from their own experience. "
        "Wrong: 'I've been thinking about data quality lately.' "
        "Right: 'The CFO opened the dashboard. The revenue number didn't match the spreadsheet.'"
    ),
    "TREND": (
        "Name the exact shift, not just 'things are changing'. Use a before/after frame: "
        "'Three years ago X was the standard. Today it's a red flag.' "
        "Or: 'The role of X has moved from [old function] to [new function] — and most teams haven't caught up.' "
        "Do NOT use: 'In today's rapidly evolving landscape', 'The pace of change is accelerating', "
        "or any phrase that doesn't name a specific thing that changed."
    ),
    "MISTAKE": (
        "Name the one specific mistake in the first sentence — concrete action + concrete consequence. "
        "Not 'people overlook X' — state the exact error: '[role] does [specific action] when [specific situation].' "
        "Then show the real outcome. Not vague failure — the specific cost or result. "
        "Example: 'Most BI teams give executives a revenue breakdown. Then wonder why nobody opens the dashboard.'"
    ),
}


async def generate(
    topic: str,
    style: str,
    tone: str,
    word_count: int,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
    context: str = "",
    suggested_angle: str = "",
) -> dict:
    """
    Generate a LinkedIn post with quality scoring.

    Args:
        topic:           Subject of the post.
        style:           Post style (e.g. "Thought Leadership", "Tips List").
        tone:            Tone (e.g. "Professional", "Conversational").
        word_count:      Approximate target length in words.
        groq_client:     Configured GroqClient instance.
        prompt_loader:   Loaded PromptLoader instance.
        context:         Research context from topic research (optional).
        suggested_angle: AI-suggested angle from topic scoring (optional).

    Returns:
        Dict with keys: post, quality_score, approved, rejection_reason,
        improvement_suggestion
    """
    # Step 1: Generate post — use context-enriched prompt when context is provided
    try:
        if context:
            prompt = prompt_loader.format(
                "post_with_context",
                topic=topic,
                suggested_angle=suggested_angle or f"Write about {topic}",
                context=context,
                style=style,
                tone=tone,
                word_count=word_count,
            )
            logger.info(f"PostGenerator: using context-enriched prompt (context={len(context)} chars)")
        else:
            prompt = prompt_loader.format(
                "post",
                topic=topic,
                style=style,
                tone=tone,
                word_count=word_count,
            )
        raw = await groq_client.complete(_SYSTEM, prompt)
        post_text = raw.strip()
        logger.info(f"PostGenerator: topic='{topic}' style='{style}' chars={len(post_text)}")
    except GroqError as e:
        logger.error(f"PostGenerator: Groq error — {e}")
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": f"Generation failed: {e}",
            "improvement_suggestion": None,
        }
    except Exception as e:
        logger.error(f"PostGenerator: unexpected error — {e}", exc_info=True)
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": f"Generation failed: {e}",
            "improvement_suggestion": None,
        }

    if not post_text:
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": "Empty post generated",
            "improvement_suggestion": None,
        }

    # Step 2: Score the generated post
    quality_score = 0.0
    rejection_reason = None
    improvement_suggestion = None
    approved = True

    try:
        scorer_prompt = prompt_loader.format(
            "post_scorer",
            post_text=post_text,
            topic=topic,
            style=style,
            target_audience="business decision makers",
        )
        raw_score = await groq_client.complete(_SYSTEM_SCORER, scorer_prompt)
        raw_score = raw_score.strip()
        if raw_score.startswith("```"):
            raw_score = raw_score.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        score_data = json.loads(raw_score)
        quality_score = float(score_data.get("total", 0))
        rejection_reason = score_data.get("rejection_reason")
        improvement_suggestion = score_data.get("improvement_suggestion")

        logger.info(
            f"PostGenerator: quality score={quality_score}/10 "
            f"publish_rec={score_data.get('publish_recommendation', 'N/A')}"
        )

        # Step 3: Quality gate
        min_score = float(cfg_get("quality.min_post_score", 7))
        if quality_score < min_score:
            approved = False
            if not rejection_reason:
                rejection_reason = f"Score {quality_score} below threshold {min_score}"
            logger.info(
                f"PostGenerator: post REJECTED — score {quality_score}: {rejection_reason}"
            )
        else:
            approved = True
            logger.info(f"PostGenerator: post APPROVED — score {quality_score}")

    except Exception as e:
        logger.warning(f"PostGenerator: scoring failed ({e}) — post not approved, user can regenerate")
        approved = False
        quality_score = 0.0
        rejection_reason = "Scoring unavailable — regenerate to retry"

    return {
        "post": post_text,
        "quality_score": quality_score,
        "approved": approved,
        "rejection_reason": rejection_reason,
        "improvement_suggestion": improvement_suggestion,
    }


async def generate_structured(
    structured_inputs: dict,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
    evidence: str = "",
    style_examples: list | None = None,
) -> dict:
    """
    Generate a LinkedIn post from structured inputs + real-world evidence.

    Args:
        structured_inputs: Dict with keys: topic, subtopic, pain_point, audience,
            hook_intent, core_insight, belief_to_challenge, proof_type,
            style, tone, word_count.
        groq_client:     Configured GroqClient instance.
        prompt_loader:   Loaded PromptLoader instance.
        evidence:        Formatted evidence block from PatternAggregator (optional).
        style_examples:  List of top published post dicts (topic, hook_intent, style,
                         tone, preview) to inject as style reference (optional).

    Returns:
        Same shape as generate(): {post, quality_score, approved, rejection_reason,
        improvement_suggestion}
    """
    topic = structured_inputs.get("topic", "")
    subtopic = structured_inputs.get("subtopic", "") or topic
    pain_point = structured_inputs.get("pain_point", "") or "Not specified"
    audience = structured_inputs.get("audience", "") or "Business decision makers"
    hook_intent = (structured_inputs.get("hook_intent", "") or "STORY").upper()
    core_insight = structured_inputs.get("core_insight", "") or ""
    belief_to_challenge = structured_inputs.get("belief_to_challenge", "") or ""
    proof_type = structured_inputs.get("proof_type", "") or "EXAMPLE"
    style = structured_inputs.get("style", "Thought Leadership")
    tone = structured_inputs.get("tone", "Professional")
    word_count = int(structured_inputs.get("word_count", 150))

    hook_instruction = _HOOK_INSTRUCTIONS.get(hook_intent, _HOOK_INSTRUCTIONS["STORY"])

    # Build optional style reference block from top published posts
    style_ref_block = ""
    if style_examples:
        lines = ["STYLE REFERENCE — Posts this author has published that performed well:"]
        for i, ex in enumerate(style_examples, 1):
            lines.append(
                f"\nExample {i} ({ex.get('style', '')} / {ex.get('hook_intent', '')} / {ex.get('tone', '')}):"
            )
            lines.append(ex.get("preview", "")[:300])
        style_ref_block = "\n".join(lines)

    # Step 1: Generate post with structured prompt
    try:
        prompt = prompt_loader.format(
            "structured_post",
            topic=topic,
            subtopic=subtopic,
            audience=audience,
            pain_point=pain_point,
            hook_intent=hook_intent,
            core_insight=core_insight or "Not specified",
            belief_to_challenge=belief_to_challenge or "None provided",
            proof_type=proof_type,
            hook_intent_instruction=hook_instruction,
            evidence_block=evidence or "No evidence available — write from domain expertise.",
            style=style,
            tone=tone,
            word_count=word_count,
            style_reference=style_ref_block,
        )
        # Use higher token limit + stronger system prompt for structured generation
        structured_max_tokens = max(int(cfg_get("ai.max_tokens", 500)), 900)
        raw = await groq_client.complete(_SYSTEM_STRUCTURED, prompt, max_tokens=structured_max_tokens)
        post_text = raw.strip()
        logger.info(
            f"PostGenerator (structured): topic='{topic}' hook={hook_intent} "
            f"chars={len(post_text)}"
        )
    except GroqError as e:
        logger.error(f"PostGenerator (structured): Groq error — {e}")
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": f"Generation failed: {e}",
            "improvement_suggestion": None,
        }
    except Exception as e:
        logger.error(f"PostGenerator (structured): unexpected error — {e}", exc_info=True)
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": f"Generation failed: {e}",
            "improvement_suggestion": None,
        }

    if not post_text:
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": "Empty post generated",
            "improvement_suggestion": None,
        }

    # Step 2: Quality gate — reuse existing scorer
    quality_score = 0.0
    rejection_reason = None
    improvement_suggestion = None
    approved = True

    try:
        scorer_prompt = prompt_loader.format(
            "post_scorer",
            post_text=post_text,
            topic=topic,
            style=style,
            target_audience=audience,
        )
        raw_score = await groq_client.complete(_SYSTEM_SCORER, scorer_prompt)
        raw_score = raw_score.strip()
        if raw_score.startswith("```"):
            raw_score = raw_score.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        score_data = json.loads(raw_score)
        quality_score = float(score_data.get("total", 0))
        rejection_reason = score_data.get("rejection_reason")
        improvement_suggestion = score_data.get("improvement_suggestion")

        min_score = float(cfg_get("quality.min_post_score", 7))
        if quality_score < min_score:
            approved = False
            if not rejection_reason:
                rejection_reason = f"Score {quality_score} below threshold {min_score}"
            logger.info(f"PostGenerator (structured): REJECTED — score {quality_score}")
        else:
            approved = True
            logger.info(f"PostGenerator (structured): APPROVED — score {quality_score}")

    except Exception as e:
        logger.warning(f"PostGenerator (structured): scoring failed ({e}) — post not approved, user can regenerate")
        approved = False
        quality_score = 0.0
        rejection_reason = "Scoring unavailable — regenerate to retry"

    return {
        "post": post_text,
        "quality_score": quality_score,
        "approved": approved,
        "rejection_reason": rejection_reason,
        "improvement_suggestion": improvement_suggestion,
    }


async def generate_pipeline(
    topic: str,
    style: str,
    tone: str,
    word_count: int,
    groq_client,
    prompt_loader: PromptLoader,
    db,
    insight_id: int | None = None,
) -> dict:
    """
    3-call pipeline: angle_generator → structured_post → post_scorer.

    Uses a ContentInsight from DB (by insight_id or best match for topic) to ground
    the generation in real signal. Falls back to generate_structured() if no insight found.

    Returns same shape as generate(): {post, quality_score, approved, rejection_reason,
    improvement_suggestion, angle_used, hook_used, insight_used}
    """
    from backend.storage.models import ContentInsight

    # Step 0: Load insight
    insight = None
    try:
        if insight_id:
            insight = db.query(ContentInsight).filter(ContentInsight.id == insight_id).first()
        if insight is None:
            # Best match by topic
            insight = (
                db.query(ContentInsight)
                .filter(ContentInsight.topic.ilike(f"%{topic}%"))
                .order_by(ContentInsight.specificity_score.desc())
                .first()
            )
    except Exception as e:
        logger.warning(f"generate_pipeline: DB lookup failed ({e}) — using fallback")

    if insight is None:
        logger.info(f"generate_pipeline: no ContentInsight for topic='{topic}' — using generate_structured fallback")
        result = await generate_structured(
            {"topic": topic, "style": style, "tone": tone, "word_count": word_count},
            groq_client=groq_client,
            prompt_loader=prompt_loader,
        )
        result.setdefault("angle_used", None)
        result.setdefault("hook_used", None)
        result.setdefault("insight_used", None)
        return result

    # Step 1: Generate angles from insight
    selected_angle = None
    hook_used = insight.hook_type or "STORY"
    angle_used = None
    try:
        angle_prompt = prompt_loader.format(
            "angle_generator",
            pain_point=insight.pain_point or "Not specified",
            mistake=insight.mistake or "none",
            false_belief=insight.false_belief or "none",
            contradiction=insight.contradiction or "none",
            scenario=insight.scenario or "none",
            audience=insight.audience_segment or "Business decision makers",
            key_insight=insight.key_insight or "Not specified",
            evidence=insight.evidence or "none",
        )
        raw_angles = await groq_client.complete(
            "You are a LinkedIn content angle strategist. Return ONLY valid JSON.",
            angle_prompt,
            max_tokens=400,
        )
        angle_data = parse_json_safe(raw_angles, context="angle_generator")
        if angle_data and isinstance(angle_data, dict):
            angles = angle_data.get("angles", [])
            best_idx = int(angle_data.get("best_angle_index", 0))
            if angles and best_idx < len(angles):
                best = angles[best_idx]
                angle_used = best.get("type", "")
                selected_angle = f"[{angle_used.upper()}] {best.get('stance', '')}"
                hook_used = angle_used.upper() if angle_used.upper() in _HOOK_INSTRUCTIONS else hook_used
                logger.info(f"generate_pipeline: angle={angle_used} hook={hook_used}")
    except Exception as e:
        logger.warning(f"generate_pipeline: angle generation failed ({e}) — continuing without angle")

    # Step 2: Generate post with structured prompt
    from backend.research.pattern_aggregator import PatternAggregator
    evidence_block = ""
    try:
        agg = PatternAggregator()
        evidence_block = agg.get_evidence_block(topic, db) or ""
    except Exception:
        pass

    structured_inputs = {
        "topic": topic,
        "subtopic": insight.subtopic or topic,
        "pain_point": insight.pain_point or "",
        "audience": insight.audience_segment or "Business decision makers",
        "hook_intent": hook_used,
        "core_insight": insight.key_insight or "",
        "belief_to_challenge": insight.false_belief or "",
        "proof_type": "EXAMPLE",
        "style": style,
        "tone": tone,
        "word_count": word_count,
        "selected_angle": selected_angle or f"Write from the {hook_used.lower()} angle.",
    }

    result = await generate_structured(
        structured_inputs=structured_inputs,
        groq_client=groq_client,
        prompt_loader=prompt_loader,
        evidence=evidence_block,
    )

    result["angle_used"] = angle_used
    result["hook_used"] = hook_used
    result["insight_used"] = {
        "id": insight.id,
        "subtopic": insight.subtopic,
        "pain_point": insight.pain_point,
        "key_insight": insight.key_insight,
    }

    # Track usage
    try:
        insight.times_used_in_generation = (insight.times_used_in_generation or 0) + 1
        from datetime import datetime
        insight.last_used_at = datetime.utcnow()
        db.commit()
    except Exception:
        pass

    return result
