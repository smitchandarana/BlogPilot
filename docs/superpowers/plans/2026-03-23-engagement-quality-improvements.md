# Engagement Quality Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix comment tone (remove "You assume/suggest/mention" openers), improve relevance scoring to reward story/emotional content, upgrade OpenRouter model to Gemini Flash, expand job-seeker blacklist, and add comment retry logic.

**Architecture:** Five isolated changes — two prompt files, one config file, one pipeline file. No new files created. All changes are backward compatible. The client routing (OpenRouter for background/scoring, Groq for generation/user-visible) already exists and is correct; we are upgrading the model and fixing the prompts it uses.

**Tech Stack:** Python 3.x, FastAPI, Playwright, Groq API (llama-3.3-70b-versatile), OpenRouter API (google/gemini-2.0-flash-exp:free), plain-text prompt templates

---

## File Map

| File | Change |
|------|--------|
| `config/settings.yaml` | Upgrade `openrouter.model` + `max_tokens`; expand `keyword_blacklist` |
| `prompts/relevance.txt` | Rewrite: add story/emotional scoring, better job-seeker disqualification |
| `prompts/comment_candidate.txt` | Add anti-"You X..." opener rules + 4th short-punchy angle |
| `backend/core/pipeline.py` | Add one retry on comment FAIL before downgrading to LIKE |

---

## Task 1: Upgrade OpenRouter model + expand keyword blacklist

**Files:**
- Modify: `config/settings.yaml`

- [ ] **Step 1: Update openrouter config block**

In `config/settings.yaml`, change the `openrouter:` block from:
```yaml
openrouter:
  model: openrouter/free
  max_tokens: 400
  temperature: 0.3
```
to:
```yaml
openrouter:
  model: google/gemini-2.0-flash-exp:free
  max_tokens: 600
  temperature: 0.2
```
Rationale: `google/gemini-2.0-flash-exp:free` is free, fast, and excellent at structured JSON output needed for scoring. Lower temperature (0.2) for more consistent scoring. More tokens (600) for the fuller scoring response.

- [ ] **Step 2: Expand keyword_blacklist**

In `config/settings.yaml`, add these entries to the existing `keyword_blacklist:` list:
```yaml
- seeking a new role
- seeking my next opportunity
- seeking new opportunities
- open for opportunities
- open to opportunities
- actively looking
- actively seeking
- exploring new opportunities
- exploring opportunities
- available for work
- available immediately
- notice period
- my next chapter
- excited to announce i've joined
- thrilled to share i've joined
- pleased to announce i've joined
- proud to announce i've joined
- happy to share that i've joined
- i'm joining
- just accepted an offer
```

- [ ] **Step 3: Verify YAML is valid**

```bash
cd d:/Projects/BlogPilot && python -c "import yaml; yaml.safe_load(open('config/settings.yaml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 4: Commit**

```bash
cd d:/Projects/BlogPilot
git add config/settings.yaml
git commit -m "feat: upgrade OpenRouter to Gemini Flash + expand job-seeker blacklist"
```

---

## Task 2: Rewrite relevance scoring prompt

**Files:**
- Modify: `prompts/relevance.txt`

The current prompt scores purely on topic relevance but misses LinkedIn's actual engagement drivers: personal stories, failures/lessons shared, genuine pain points expressed in first person. It also misses job-seeker phrases beyond the exact blacklist strings.

- [ ] **Step 1: Replace prompts/relevance.txt**

Overwrite with the following content (full file replacement):

```
You are a LinkedIn post relevance scoring engine for a B2B engagement automation system.

Your task: Evaluate how relevant a LinkedIn post is to a set of target topics, then return a structured score.

---

TARGET TOPICS:
{topics}

POST AUTHOR: {author_name}

POST CONTENT:
{post_text}

---

STEP 1 — DISQUALIFICATION CHECK (Run this first)

Immediately return score 0 if the post is primarily any of the following:

HIRING & RECRUITMENT
- Job postings ("We're hiring", "Open role", "Join our team", "Apply now", "Now hiring")
- Candidate availability posts ("seeking a new role", "seeking my next opportunity", "open to opportunities", "open for opportunities", "actively looking", "actively seeking", "exploring new opportunities", "available for work", "available immediately", "looking for my next chapter")
- Candidate shoutouts ("Congrats on the new role", "Welcome to the team", "thrilled to announce I've joined", "excited to share I've joined", "just accepted an offer")
- Recruiting agency promotions or staffing posts with direct contact info (phone numbers, email addresses)
- Resume tips, interview advice, salary negotiation (unless your topics are HR/recruiting)

SELF-PROMOTION & ADS
- Product launches framed as ads ("Introducing our new feature...")
- Discount/offer announcements ("50% off", "Limited time deal", "Use code...")
- Event promotions with no educational value ("Register now", "Seats are filling up")
- Award announcements ("We won Best SaaS 2024", "Proud to be recognized...")
- Partnership or client win announcements with no insight

VANITY & PERSONAL MILESTONES
- Work anniversaries with generic reflection and no substantive insight
- Follower milestones ("Just hit 10K followers!")
- Birthday/holiday wishes
- Personal travel or lifestyle posts unrelated to work topics
- Gratitude posts with no substance ("So grateful for this community")

REPOSTS WITH NO ADDED VALUE
- Posts that are pure reshares with zero original commentary
- "Tag someone who needs this" engagement bait
- Polls with no insight or context ("What do you prefer? A or B?")
- Motivational quote images with no original thought

LOW-SIGNAL ENGAGEMENT BAIT
- "Like if you agree" posts
- Listicles with only obvious, surface-level points
- "Hot take:" posts with no actual substance behind the take

COMPANY NEWS WITHOUT INSIGHT
- Press release reposts or funding announcements with no market commentary
- "We're expanding to X market" with no relevant context

---

STEP 2 — RELEVANCE SCORING (Only if post passes Step 1)

Score from 0 to 10 based on TWO dimensions: topic alignment AND content quality.

TOPIC ALIGNMENT (0–6 base score):
| 0–1 | No connection to target topics |
| 2–3 | Mentions a topic keyword but core message is unrelated |
| 4–5 | Touches the topic area but lacks depth or specificity |
| 6   | Directly discusses a target topic with real substance |

QUALITY BONUS (adds 0–4 points on top of base, only if base ≥ 4):
Award +1 to +4 based on how many of these signals are present:

+1  Original data, personal numbers, or a specific case study from the author's own experience
+1  First-person story format: author shares a failure, lesson, challenge, or turning point
+1  Genuine pain point expressed: author or audience is wrestling with a real decision or problem
+1  Contrarian or non-obvious perspective that challenges a widely held assumption

A score of 9–10 requires both strong topic alignment (base ≥ 6) AND at least two quality bonuses.
A well-written personal story on-topic scores higher than a generic industry observation.

SCORING RULES:
1. Score on SEMANTIC meaning — not keyword presence alone.
2. Prioritize posts signaling a PAIN POINT, CHALLENGE, QUESTION, or BUYING SIGNAL related to your topics.
3. Reward first-person storytelling about real work experiences — these drive the highest LinkedIn engagement.
4. Author identity or follower count does NOT influence the score.
5. A post can be well-written and still score low if it doesn't match the target topics.
6. A post can be emotionally engaging and still score low if it has no B2B relevance.

---

OUTPUT FORMAT:

Return ONLY a valid JSON object. No markdown. No commentary. No text before or after.

{{"score": <integer 0-10>, "reason": "<one concise sentence explaining why this score was given>"}}
```

- [ ] **Step 2: Verify prompt loads without error**

```bash
cd d:/Projects/BlogPilot && python -c "
from backend.ai.prompt_loader import PromptLoader
pl = PromptLoader()
pl.load_all()
t = pl.format('relevance', post_text='test', author_name='test', topics='test')
print('relevance prompt OK, len=', len(t))
"
```
Expected: `relevance prompt OK, len=` followed by a number > 500

- [ ] **Step 3: Commit**

```bash
cd d:/Projects/BlogPilot
git add prompts/relevance.txt
git commit -m "feat: rewrite relevance prompt — story/emotional scoring + better job-seeker detection"
```

---

## Task 3: Fix comment candidate prompt

**Files:**
- Modify: `prompts/comment_candidate.txt`

Root cause: `comment_candidate.txt` (the primary 3-candidate generation path) tells the model to address the author in second person but never blocks the "You assume / You suggest / You mention / You emphasize" openers. These openers sound like analytical critique, not peer conversation. They generate defensiveness and low reply rates.

Also adding a 4th angle: **short punchy 1-liner** — this covers the score-7 use case where a full 3-angle comment is overkill.

- [ ] **Step 1: Replace prompts/comment_candidate.txt**

Overwrite with the following content (full file replacement):

```
You are writing LinkedIn comments as a senior BI/reporting professional.

Generate {candidate_count} distinct comment candidates for the post below.
Each candidate takes a DIFFERENT angle:
  - Angle A (insight):       Add a specific fact, number, or experience from your own work that is directly relevant
  - Angle B (contrarian):    Respectfully challenge one specific claim or assumption — name what you've seen instead
  - Angle C (missing_piece): Name the one thing the post correctly identifies, then name the specific gap or hard part it doesn't address. Must be grounded in real implementation experience — not a general observation.
  - Angle D (punchy):        One short, punchy sentence (under 20 words). A sharp observation, a specific stat, or a direct reaction. No questions. No padding.

HARD RULES for ALL candidates:

BANNED OPENERS — never start a comment with any of these patterns:
  - "You assume..." / "You suggest..." / "You mention..." / "You note..."
  - "You emphasize..." / "You require..." / "You highlight..." / "You argue..."
  - "You make a good point..." / "You correctly identify..."
  - Any opener that implies the author got something wrong or that you are reviewing their work
  - "Great post" / "Love this" / "So true" / "Absolutely" / "This is amazing"
  - "I'd love to hear" / "Can you elaborate" / "Can you share more" / "How do you see"

INSTEAD, open with YOUR perspective, experience, or reaction:
  - "In my experience with [specific thing]..."
  - "Something that keeps coming up when [context]..."
  - "This matches what I've seen when..."
  - "[Specific observation about the topic] — [what that means]"
  - Or lead directly with the insight itself

OTHER HARD RULES:
  - NEVER summarize or rephrase what the author already said. They know what they wrote.
  - NEVER use hollow phrases: "game-changer", "paradigm shift", "at the end of the day", "resonates", "so important"
  - Length for A/B/C: 30-70 words. Say ONE thing well. No walls of text.
  - Length for D (punchy): under 20 words. Sharp, specific, stops the scroll.
  - Sound like a real person mid-conversation, not a consultant writing a memo
  - No hashtags, no emojis, no links
  - For Angle C (missing piece): name ONE specific gap, not a list of concerns. Concrete enough that someone who lived through it would nod.
  - For Angle D (punchy): must contain something specific — a number, a named tool, a concrete situation. Not a generic reaction.

Post:
{post_text}

Author: {author_name}, {author_title}

Your focus topics: {topics}
Tone: {tone}

Return ONLY valid JSON, no preamble, no markdown:
{{"candidates": [{{"angle": "insight", "text": "..."}}, {{"angle": "contrarian", "text": "..."}}, {{"angle": "missing_piece", "text": "..."}}, {{"angle": "punchy", "text": "..."}}]}}
```

- [ ] **Step 2: Update candidate_count default in comment_generator.py**

The config key `quality.comment_candidates` defaults to 3. With the new 4-angle prompt, we now generate 4. Update the default fallback in [backend/ai/comment_generator.py](backend/ai/comment_generator.py) line 309:

```python
# Change this line:
candidate_count = int(cfg_get("quality.comment_candidates", 3))
# To:
candidate_count = int(cfg_get("quality.comment_candidates", 4))
```

Also update `config/settings.yaml`:
```yaml
# Change:
  comment_candidates: 3
# To:
  comment_candidates: 4
```

- [ ] **Step 3: Verify prompt loads without error**

```bash
cd d:/Projects/BlogPilot && python -c "
from backend.ai.prompt_loader import PromptLoader
pl = PromptLoader()
pl.load_all()
t = pl.format('comment_candidate', candidate_count=4, post_text='test post', author_name='John', author_title='CEO', topics='analytics', tone='professional')
print('comment_candidate prompt OK, len=', len(t))
print('Checking banned patterns not in rules section...')
assert 'BANNED OPENERS' in t
print('PASS')
"
```
Expected: prints OK and PASS

- [ ] **Step 4: Commit**

```bash
cd d:/Projects/BlogPilot
git add prompts/comment_candidate.txt backend/ai/comment_generator.py config/settings.yaml
git commit -m "feat: fix comment candidate prompt — ban You-X openers, add punchy angle, 4 candidates"
```

---

## Task 4: Add comment retry logic in pipeline

**Files:**
- Modify: `backend/core/pipeline.py` (lines ~514-528)

Currently if `ie.comment_post()` returns False (FAILED), the pipeline logs FAILED and moves on. One retry with a short delay before downgrading to LIKE.

- [ ] **Step 1: Replace the comment execution block in _process_post**

Find this block in `backend/core/pipeline.py` (around line 514):

```python
    if action in ("COMMENT", "LIKE_AND_COMMENT") and comment_text:
        ok = await ie.comment_post(page, url, comment_text, db=db, topic_tag=matched_topic)
        if ok:
            acted = True
            # Log comment quality metrics for self-learning
            try:
                from backend.storage import quality_log
                quality_log.log_comment(
                    db=db, post_id=url, post_text=post.get("text", ""),
                    comment_used=comment_text, quality_score=comment_quality_score,
                    candidate_count=comment_candidate_count, topic=matched_topic,
                    all_candidates=None, angle=comment_angle,
                )
            except Exception as e:
                logger.debug(f"Pipeline: comment quality log error — {e}")
```

Replace with:

```python
    if action in ("COMMENT", "LIKE_AND_COMMENT") and comment_text:
        ok = await ie.comment_post(page, url, comment_text, db=db, topic_tag=matched_topic)
        if not ok:
            # Retry once after a short delay before giving up
            logger.info(f"Pipeline: comment failed for '{author}' — retrying in 3s")
            await asyncio.sleep(3)
            ok = await ie.comment_post(page, url, comment_text, db=db, topic_tag=matched_topic)
            if not ok:
                logger.warning(f"Pipeline: comment retry also failed for '{author}' — downgrading to LIKE")
        if ok:
            acted = True
            # Log comment quality metrics for self-learning
            try:
                from backend.storage import quality_log
                quality_log.log_comment(
                    db=db, post_id=url, post_text=post.get("text", ""),
                    comment_used=comment_text, quality_score=comment_quality_score,
                    candidate_count=comment_candidate_count, topic=matched_topic,
                    all_candidates=None, angle=comment_angle,
                )
            except Exception as e:
                logger.debug(f"Pipeline: comment quality log error — {e}")
```

Note: `asyncio` is already imported at the top of pipeline.py.

- [ ] **Step 2: Verify pipeline imports still resolve**

```bash
cd d:/Projects/BlogPilot && python -c "
import sys; sys.path.insert(0, '.')
import ast
with open('backend/core/pipeline.py') as f:
    src = f.read()
ast.parse(src)
print('pipeline.py syntax OK')
"
```
Expected: `pipeline.py syntax OK`

- [ ] **Step 3: Commit**

```bash
cd d:/Projects/BlogPilot
git add backend/core/pipeline.py
git commit -m "fix: retry comment once on failure before downgrading to LIKE"
```

---

## Task 5: Smoke test all changes together

- [ ] **Step 1: Run the existing test suite to verify no regressions**

```bash
cd d:/Projects/BlogPilot && python -m pytest tests/ -v --tb=short -k "not test_e2e" 2>&1 | tail -30
```
Expected: all tests pass (94 previously passing tests should still pass)

- [ ] **Step 2: Verify comment_generator uses 4 candidates**

```bash
cd d:/Projects/BlogPilot && python -c "
from backend.utils.config_loader import load_config, get as cfg_get
load_config()
count = int(cfg_get('quality.comment_candidates', 4))
print(f'comment_candidates config = {count}')
assert count == 4, f'Expected 4, got {count}'
print('PASS')
"
```
Expected: `comment_candidates config = 4` and `PASS`

- [ ] **Step 3: Verify OpenRouter model config**

```bash
cd d:/Projects/BlogPilot && python -c "
from backend.utils.config_loader import load_config, get as cfg_get
load_config()
model = cfg_get('openrouter.model', '')
print(f'openrouter.model = {model}')
assert 'gemini' in model, f'Expected gemini model, got {model}'
print('PASS')
"
```
Expected: `openrouter.model = google/gemini-2.0-flash-exp:free` and `PASS`

- [ ] **Step 4: Verify blacklist expansion**

```bash
cd d:/Projects/BlogPilot && python -c "
from backend.utils.config_loader import load_config, get as cfg_get
load_config()
bl = cfg_get('keyword_blacklist', [])
assert 'seeking a new role' in bl, 'Missing: seeking a new role'
assert 'actively looking' in bl, 'Missing: actively looking'
assert 'open for opportunities' in bl, 'Missing: open for opportunities'
print(f'Blacklist has {len(bl)} entries — PASS')
"
```
Expected: `Blacklist has N entries — PASS` where N > 20

- [ ] **Step 5: Final commit if all checks pass**

```bash
cd d:/Projects/BlogPilot
git log --oneline -5
```
Verify the last 4 commits are the ones from this plan. All done.
