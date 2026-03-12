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
    (15, "Write exactly 1 punchy sentence. No fluff."),
    (30, "Keep it to 2 sentences max."),
    (25, "Write 2–3 sentences."),
    (20, "Write 3–4 sentences with some depth."),
    (10, "Write 4–5 sentences — go deeper, share a real thought."),
]

_STYLE_OPTIONS = [
    "Share a quick personal observation related to the post",
    "Ask a specific, thoughtful question about something in the post",
    "Add a relevant data point, stat, or number you've seen",
    "Relate the topic to a trend you've noticed recently",
    "Offer a slightly different perspective or gentle pushback",
    "Share a brief real-world experience or anecdote",
    "Build on the author's point with a specific example",
    "Agree with one part and expand on why it matters",
    "Connect this to something happening in your industry",
    "Point out an implication the author didn't mention",
]

_ENERGY_OPTIONS = [
    "Casual and brief — like a quick reply between meetings",
    "Thoughtful and measured — take your time with the words",
    "Enthusiastic but genuine — you actually care about this topic",
    "Direct and to-the-point — no padding, say what you mean",
    "Curious and questioning — you want to learn more",
    "Warm and conversational — like talking to a colleague",
    "Confident and opinionated — you have a clear stance",
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

    # ── Step 1: Load winning examples for few-shot ──
    winning_examples = _load_winning_examples(db)
    examples_block = ""
    if winning_examples:
        examples_block = "\n\nHere are examples of high-performing comments for reference:\n"
        for i, ex in enumerate(winning_examples, 1):
            examples_block += f"  Example {i}: {ex}\n"

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
