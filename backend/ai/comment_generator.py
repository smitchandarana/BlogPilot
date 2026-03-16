"""
Comment generator — produces a genuine LinkedIn comment for a given post.

Sprint 10: Enhanced with 3-candidate pipeline, scoring, and diversity guard.
Falls back to single-comment generation (old prompt) on any failure.

Usage:
    result = await generate(post_text, author_name, topics, tone, groq_client, prompt_loader)
    # result is a dict: {"comment": str, "quality_score": float, "angle": str, ...}
"""
import json
import random
from typing import Union, Optional

from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_SYSTEM = (
    "You are a professional LinkedIn commenter. "
    "Write only the comment text — no intro, no quotes, no explanation."
)

_SYSTEM_CANDIDATE = (
    "You are a LinkedIn engagement expert. "
    "Return ONLY valid JSON. No preamble, no markdown fences."
)

_SYSTEM_SCORER = (
    "You are a comment quality evaluator. "
    "Return ONLY valid JSON. No preamble, no markdown fences."
)

# ── Randomization pools (used by fallback single-comment path) ────────────

_LENGTH_OPTIONS = [
    (25, "Write exactly 1 punchy sentence. No fluff."),
    (40, "Keep it to 2 sentences max."),
    (25, "Write 2–3 short sentences."),
    (10, "Write 3 sentences with some depth."),
]

_STYLE_OPTIONS = [
    "Drop a specific number or stat from your own work that supports or challenges the post",
    "Name a concrete tool, framework, or method you'd use differently",
    "Disagree with one specific claim — say what you've seen instead",
    "Share a 1-sentence war story from a real project that's relevant",
    "Point out a consequence or second-order effect the author missed",
    "Connect this to a specific trend you've noticed in the last 6 months",
    "Mention a specific company, team, or project where you saw this play out",
    "Challenge an assumption buried in the post — name it explicitly",
    "Add a caveat the author skipped — when does their advice NOT work?",
    "State your actual opinion on the topic — agree or disagree, but be specific",
]

_ENERGY_OPTIONS = [
    "Casual and brief — like a quick reply between meetings",
    "Direct and to-the-point — no padding, say what you mean",
    "Confident and opinionated — you have a clear stance",
    "Slightly provocative — push back on something specific",
    "Matter-of-fact — state what you know, no hedging",
    "Warm but brief — like talking to a colleague in passing",
]


def _randomize_comment_params() -> dict:
    """
    Generate randomized length, style, and energy instructions.
    Called once per comment to ensure every comment feels different.
    """
    weights = [opt[0] for opt in _LENGTH_OPTIONS]
    instructions = [opt[1] for opt in _LENGTH_OPTIONS]
    length_instruction = random.choices(instructions, weights=weights, k=1)[0]

    style_count = random.choice([1, 1, 1, 2])
    styles = random.sample(_STYLE_OPTIONS, k=style_count)
    style_instruction = ". ".join(styles)

    energy_instruction = random.choice(_ENERGY_OPTIONS)

    return {
        "length_instruction": length_instruction,
        "style_instruction": style_instruction,
        "energy_instruction": energy_instruction,
    }


def _clean(text: str) -> str:
    """Strip surrounding quotes and whitespace from model output."""
    text = text.strip()
    if len(text) >= 2 and text[0] in ('"', "'") and text[-1] == text[0]:
        text = text[1:-1].strip()
    return text


# ── Diversity check ───────────────────────────────────────────────────────

def _check_diversity(new_comment: str, db) -> bool:
    """
    Return True if new_comment is diverse enough from recent comments.
    Uses simple word-overlap similarity. Threshold from config.
    """
    if db is None:
        return True

    try:
        from backend.storage.models import CommentQualityLog

        max_recent = int(cfg_get("quality.max_recent_comments_for_diversity", 20))
        threshold = float(cfg_get("quality.diversity_threshold", 0.7))

        recent = (
            db.query(CommentQualityLog.comment_used)
            .order_by(CommentQualityLog.created_at.desc())
            .limit(max_recent)
            .all()
        )

        new_words = set(new_comment.lower().split())
        if not new_words:
            return True

        for (recent_text,) in recent:
            if not recent_text:
                continue
            recent_words = set(recent_text.lower().split())
            overlap = len(new_words & recent_words) / len(new_words)
            if overlap > threshold:
                return False

        return True
    except Exception as e:
        logger.debug(f"Diversity check skipped: {e}")
        return True


# ── Winning examples loader ──────────────────────────────────────────────

def _load_winning_examples(db) -> list:
    """
    Load up to 3 recent high-scoring comments that got replies.
    Returns list of comment text strings.
    """
    if db is None:
        return []

    try:
        from backend.storage.models import CommentQualityLog

        min_score = float(cfg_get("quality.winning_example_min_score", 8))
        rows = (
            db.query(CommentQualityLog.comment_used)
            .filter(
                CommentQualityLog.quality_score >= min_score,
                CommentQualityLog.got_reply == True,
            )
            .order_by(CommentQualityLog.created_at.desc())
            .limit(3)
            .all()
        )
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.debug(f"Winning examples load skipped: {e}")
        return []


def _load_angle_insight(db) -> str:
    """
    Query CommentQualityLog for the best-performing angle based on reply rate.
    Returns a prompt hint string or "" if insufficient data.
    """
    if db is None:
        return ""

    try:
        from backend.storage.models import CommentQualityLog
        from sqlalchemy import func

        # Need at least 10 comments with reply data
        checked = (
            db.query(CommentQualityLog)
            .filter(CommentQualityLog.got_reply.isnot(None))
            .count()
        )
        if checked < 10:
            return ""

        # Find angle with best reply rate (minimum 3 samples)
        # Use two queries for simplicity and SQLite compatibility
        angle_rows = (
            db.query(
                CommentQualityLog.angle,
                func.count(CommentQualityLog.id).label("total"),
            )
            .filter(CommentQualityLog.got_reply.isnot(None))
            .group_by(CommentQualityLog.angle)
            .having(func.count(CommentQualityLog.id) >= 3)
            .all()
        )

        if not angle_rows:
            return ""

        best_angle = ""
        best_rate = 0.0
        for angle, total in angle_rows:
            reply_count = (
                db.query(CommentQualityLog)
                .filter(
                    CommentQualityLog.angle == angle,
                    CommentQualityLog.got_reply == True,
                )
                .count()
            )
            rate = reply_count / total if total > 0 else 0
            if rate > best_rate:
                best_rate = rate
                best_angle = angle

        if best_angle and best_rate > 0.1:
            return (
                f"Insight: Comments using the '{best_angle}' approach have a "
                f"{best_rate:.0%} reply rate. Consider this angle."
            )

        return ""
    except Exception as e:
        logger.debug(f"Angle insight load skipped: {e}")
        return ""


# ── Fallback: single-comment generation (old path) ──────────────────────

async def _generate_single(
    post_text: str,
    author_name: str,
    topics: str,
    tone: str,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
) -> dict:
    """Fallback: generate one comment using the original comment.txt prompt."""
    params = _randomize_comment_params()
    try:
        prompt = prompt_loader.format(
            "comment",
            post_text=post_text,
            author_name=author_name,
            topics=topics,
            tone=tone,
            length_instruction=params["length_instruction"],
            style_instruction=params["style_instruction"],
            energy_instruction=params["energy_instruction"],
        )
        raw = await groq_client.complete(_SYSTEM, prompt)
        comment = _clean(raw)
        return {
            "comment": comment,
            "quality_score": 0.0,
            "angle": "unknown",
            "candidate_count": 1,
            "all_candidates": [{"angle": "unknown", "text": comment}],
        }
    except Exception as e:
        logger.error(f"CommentGenerator fallback failed: {e}")
        return {
            "comment": "",
            "quality_score": 0.0,
            "angle": "unknown",
            "candidate_count": 0,
            "all_candidates": [],
        }


# ── Main generate function ───────────────────────────────────────────────

async def generate(
    post_text: str,
    author_name: str,
    topics: Union[str, list],
    tone: str,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
    author_title: str = "",
    db=None,
) -> dict:
    """
    Generate a LinkedIn comment for *post_text* using the 3-candidate pipeline.

    Args:
        post_text:     Full text of the LinkedIn post.
        author_name:   Display name of the post author.
        topics:        Comma-separated string or list of target topics.
        tone:          "professional" | "conversational" | "bold"
        groq_client:   Configured GroqClient instance.
        prompt_loader: Loaded PromptLoader instance.
        author_title:  Job title of the post author (optional, may be empty).
        db:            SQLAlchemy session for diversity/examples queries (optional).

    Returns:
        Dict with keys: comment, quality_score, angle, candidate_count, all_candidates
    """
    if isinstance(topics, list):
        topics = ", ".join(str(t) for t in topics)

    candidate_count = int(cfg_get("quality.comment_candidates", 3))

    # ── Step 1: Load winning examples + angle insights for few-shot ──
    winning_examples = _load_winning_examples(db)
    examples_block = ""
    if winning_examples:
        examples_block = "\n\nHere are examples of high-performing comments for reference:\n"
        for i, ex in enumerate(winning_examples, 1):
            examples_block += f"  Example {i}: {ex}\n"

    # Add best-performing angle insight from engagement data
    angle_insight = _load_angle_insight(db)
    if angle_insight:
        examples_block += f"\n{angle_insight}\n"

    # ── Step 2: Generate candidates ──
    try:
        candidate_prompt = prompt_loader.format(
            "comment_candidate",
            candidate_count=candidate_count,
            post_text=post_text,
            author_name=author_name,
            author_title=author_title or "LinkedIn user",
            topics=topics,
            tone=tone,
        )
        if examples_block:
            candidate_prompt += examples_block

        raw = await groq_client.complete(_SYSTEM_CANDIDATE, candidate_prompt)
        raw = raw.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)
        candidates = parsed.get("candidates", [])
        if not candidates or not isinstance(candidates, list):
            raise ValueError("No candidates in response")

        logger.info(f"CommentGenerator: generated {len(candidates)} candidates for '{author_name}'")
    except Exception as e:
        logger.warning(f"CommentGenerator: candidate generation failed ({e}), using fallback")
        return await _generate_single(post_text, author_name, topics, tone, groq_client, prompt_loader)

    # ── Step 3: Score all candidates ──
    winner_index = 0
    scores = []
    try:
        scorer_prompt = prompt_loader.format(
            "comment_scorer",
            post_text=post_text,
            candidates_json=json.dumps(candidates, ensure_ascii=False),
        )
        raw_score = await groq_client.complete(_SYSTEM_SCORER, scorer_prompt)
        raw_score = raw_score.strip()
        if raw_score.startswith("```"):
            raw_score = raw_score.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        score_parsed = json.loads(raw_score)
        scores = score_parsed.get("scores", [])
        winner_index = int(score_parsed.get("winner_index", 0))

        # Log individual scores
        for s in scores:
            idx = s.get("index", "?")
            total = s.get("total", 0)
            logger.info(f"CommentGenerator: Candidate {idx} scored {total}/10")

        # Clamp winner_index to valid range
        if winner_index < 0 or winner_index >= len(candidates):
            winner_index = 0
    except Exception as e:
        logger.warning(f"CommentGenerator: scoring failed ({e}), picking first candidate")
        winner_index = 0

    # ── Step 3b: Check if all candidates were rejected ──
    min_quality = float(cfg_get("quality.min_comment_score", 4))
    if scores:
        best_score = max(s.get("total", 0) for s in scores)
        if best_score < min_quality:
            reasons = [s.get("reject_reason", "low score") for s in scores if s.get("reject_reason")]
            logger.warning(
                f"CommentGenerator: ALL candidates scored below {min_quality} "
                f"(best={best_score}). Reasons: {reasons}. Returning empty."
            )
            return {
                "comment": "",
                "quality_score": 0.0,
                "angle": "rejected",
                "candidate_count": len(candidates),
                "all_candidates": candidates,
                "rejected": True,
                "reject_reasons": reasons,
            }

    # ── Step 4: Diversity check ──
    winning_comment = candidates[winner_index].get("text", "")
    winning_angle = candidates[winner_index].get("angle", "unknown")
    winning_score = scores[winner_index].get("total", 0) if winner_index < len(scores) else 0

    if not _check_diversity(winning_comment, db):
        logger.info("CommentGenerator: winner failed diversity check, trying alternatives")
        # Sort candidates by score descending, skip the winner
        scored_indices = list(range(len(candidates)))
        if scores:
            scored_indices.sort(
                key=lambda i: scores[i].get("total", 0) if i < len(scores) else 0,
                reverse=True,
            )
        found_diverse = False
        for idx in scored_indices:
            if idx == winner_index:
                continue
            alt_text = candidates[idx].get("text", "")
            if _check_diversity(alt_text, db):
                winning_comment = alt_text
                winning_angle = candidates[idx].get("angle", "unknown")
                winning_score = scores[idx].get("total", 0) if idx < len(scores) else 0
                found_diverse = True
                logger.info(f"CommentGenerator: selected alternative candidate {idx}")
                break
        if not found_diverse:
            logger.warning("CommentGenerator: all candidates failed diversity check, using winner anyway")

    winning_comment = _clean(winning_comment)
    logger.info(
        f"CommentGenerator: final comment for '{author_name}' — "
        f"angle={winning_angle}, score={winning_score}, chars={len(winning_comment)}"
    )

    return {
        "comment": winning_comment,
        "quality_score": float(winning_score),
        "angle": winning_angle,
        "candidate_count": len(candidates),
        "all_candidates": candidates,
    }
