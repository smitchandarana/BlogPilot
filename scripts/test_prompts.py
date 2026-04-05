"""
Self-improving prompt quality tester.

Usage:
    python scripts/test_prompts.py

Tests all content-generating prompts against real LinkedIn examples,
scores each output, and iterates up to MAX_ROUNDS if quality is low.

Model: llama-3.1-8b-instant (Groq free tier)
"""
import io
import json
import os
import re
import sys
import time
import requests

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL = "llama-3.1-8b-instant"
MAX_ROUNDS = 3   # Max self-improvement iterations per test
PASS_SCORE = 7   # Minimum acceptable score out of 10
API_DELAY = 3    # Seconds between Groq calls (free tier rate limit)

# ── Realistic test data ──────────────────────────────────────────────────────

SAMPLE_POST_1 = (
    "We just cut our monthly reporting cycle from 5 days to 4 hours. "
    "No new software. No headcount. Just redesigned the data flow and killed "
    "60% of the reports nobody was reading. The hard part was convincing the "
    "team to delete their work."
)
SAMPLE_POST_2 = (
    "After 5 years building BI dashboards, I realized the biggest problem is "
    "never the data. It is always the questions being asked. I spent weeks "
    "building a beautiful Power BI dashboard for a CFO only to hear: this is "
    "nice but can you just show me if we are on track or not? Now I always "
    "start with the decision, not the data."
)
SAMPLE_POST_3 = (
    "Most KPI dashboards fail because teams track what is easy to measure, "
    "not what actually drives the business. Revenue is easy. Customer lifetime "
    "value is hard. Guess which one matters more."
)

TOPICS = "Data Analytics, Business Intelligence, Power BI, Dashboard Design, Reporting"
AUTHOR_1 = ("James Okafor", "Head of Business Intelligence")
AUTHOR_2 = ("Sarah Chen", "Director of Analytics")
AUTHOR_3 = ("Marcus Williams", "CFO")


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_prompt(name: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", f"{name}.txt")
    with open(path, encoding="utf-8") as f:
        return f.read()


def call_groq(system: str, user: str, max_tokens: int = 600, temperature: float = 0.7) -> str:
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return ""


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def score_text(text: str, context: str = "") -> dict:
    """Ask the model to evaluate a piece of generated content for human-likeness."""
    system = "You are a LinkedIn content quality evaluator. Return ONLY valid JSON."
    prompt = f"""Evaluate this LinkedIn {context} for human authenticity and engagement quality.

Text to evaluate:
\"\"\"{text}\"\"\"

Score each dimension 0-2 (total max 10):
- human_voice: Sounds like a real person, not AI-generated (0=obvious AI, 2=could be real person)
- specificity: References concrete details, not vague generalities (0=generic, 2=very specific)
- no_ai_tells: Free of classic AI phrases like 'resonates', 'actionable insights', 'in my experience', 'game-changer', 'paradigm shift', 'at the end of the day' (0=multiple AI tells, 2=none)
- engagement_value: Would make the author want to respond or the reader want to share (0=low, 2=high)
- opener_quality: Does NOT start with a banned pattern like "Great post", "So true", "I've seen...", "In my experience..." (0=banned opener, 2=strong opener)

Issues: list any specific problems found (empty array if none)

Return ONLY JSON:
{{"human_voice": 0, "specificity": 0, "no_ai_tells": 0, "engagement_value": 0, "opener_quality": 0, "total": 0, "issues": [], "verdict": "pass|fail"}}"""

    raw = call_groq(system, prompt, max_tokens=300, temperature=0.3)
    data = parse_json(raw)
    if data and "total" not in data:
        data["total"] = sum(data.get(k, 0) for k in ["human_voice", "specificity", "no_ai_tells", "engagement_value", "opener_quality"])
    return data


def refine_text(text: str, issues: list, context: str, extra_context: str = "") -> str:
    """Ask the model to rewrite the text fixing the identified issues."""
    issues_str = "\n".join(f"- {i}" for i in issues) if issues else "- Generic, AI-sounding phrasing"
    system = f"You are a LinkedIn {context} expert. Rewrite to fix the specific issues listed. Output ONLY the rewritten text, no explanation."
    prompt = f"""Original {context}:
\"\"\"{text}\"\"\"

{extra_context}

Issues to fix:
{issues_str}

Rules for rewrite:
- Keep the same core substance and angle
- Fix ONLY the listed issues
- Do NOT add emojis
- Do NOT use: "resonates", "actionable", "game-changer", "in my experience", "I've seen"
- Output ONLY the rewritten text"""

    return call_groq(system, prompt, max_tokens=400, temperature=0.8)


def _safe(s: str) -> str:
    """Replace non-ASCII characters to avoid Windows console encoding errors."""
    return s.encode("ascii", errors="replace").decode("ascii")


def print_result(label: str, text: str, scores: dict, round_num: int):
    verdict = scores.get("verdict", "?")
    total = scores.get("total", 0)
    issues = scores.get("issues", [])
    status = "PASS" if verdict == "pass" or total >= PASS_SCORE else "FAIL"
    print(f"\n{'='*60}")
    print(f"  [{label}] Round {round_num} -- Score: {total}/10 -- {status}")
    print(f"{'='*60}")
    print(f"  Text: {_safe(text[:300])}{'...' if len(text) > 300 else ''}")
    print(f"  human_voice={scores.get('human_voice',0)}  specificity={scores.get('specificity',0)}  "
          f"no_ai_tells={scores.get('no_ai_tells',0)}  engagement={scores.get('engagement_value',0)}  "
          f"opener={scores.get('opener_quality',0)}")
    if issues:
        print(f"  Issues: {[_safe(str(i)) for i in issues]}")


# ── Test functions ────────────────────────────────────────────────────────────

def test_comment():
    print("\n" + "=" * 70)
    print("TEST 1: COMMENT GENERATION (single-pass fallback path)")
    print("=" * 70)
    template = load_prompt("comment")
    filled = (template
        .replace("{topics}", TOPICS)
        .replace("{tone}", "conversational")
        .replace("{length_instruction}", "Write 2-3 short sentences.")
        .replace("{style_instruction}", "Name a concrete consequence or second-order effect the author missed")
        .replace("{energy_instruction}", "Direct and to-the-point — no padding, say what you mean")
        .replace("{author_name}", AUTHOR_1[0])
        .replace("{post_text}", SAMPLE_POST_1))

    system = "You are a professional LinkedIn commenter. Write only the comment text -- no intro, no quotes, no explanation."
    text = call_groq(system, filled)
    time.sleep(API_DELAY)
    scores = score_text(text, "comment")
    print_result("COMMENT", text, scores, 1)

    best_text, best_scores = text, scores
    for round_num in range(2, MAX_ROUNDS + 1):
        if best_scores.get("total", 0) >= PASS_SCORE:
            print(f"  [OK] Passed on round {round_num - 1}")
            break
        issues = scores.get("issues", ["Generic or AI-sounding"])
        print(f"\n  Refining (round {round_num})...")
        text = refine_text(text, issues, "comment",
                          f"Post: {SAMPLE_POST_1}\nAuthor: {AUTHOR_1[0]}")
        time.sleep(API_DELAY)
        scores = score_text(text, "comment")
        print_result("COMMENT", text, scores, round_num)
        if scores.get("total", 0) > best_scores.get("total", 0):
            best_text, best_scores = text, scores

    return best_text, best_scores


def test_comment_candidates():
    print("\n" + "=" * 70)
    print("TEST 2: COMMENT CANDIDATES (multi-candidate pipeline)")
    print("=" * 70)
    template = load_prompt("comment_candidate")
    filled = (template
        .replace("{candidate_count}", "4")
        .replace("{post_text}", SAMPLE_POST_1)
        .replace("{author_name}", AUTHOR_1[0])
        .replace("{author_title}", AUTHOR_1[1])
        .replace("{topics}", TOPICS)
        .replace("{tone}", "conversational"))

    system = "You are a LinkedIn engagement expert. Return ONLY valid JSON. No preamble, no markdown fences."
    raw = call_groq(system, filled, max_tokens=700)
    data = parse_json(raw)
    candidates = data.get("candidates", [])

    if not candidates:
        print("  ERROR: No candidates returned")
        return [], {}

    print(f"\n  Generated {len(candidates)} candidates:")
    best_text = ""
    best_score = 0
    all_scores = []
    for i, c in enumerate(candidates):
        text = c.get("text", "")
        angle = c.get("angle", "?")
        time.sleep(API_DELAY)
        scores = score_text(text, f"comment (angle: {angle})")
        total = scores.get("total", 0)
        all_scores.append((i, angle, text, total, scores))
        status = "PASS" if total >= PASS_SCORE else "FAIL"
        print(f"\n  Candidate {i} [{angle}] -- {total}/10 [{status}]")
        print(f"    Text: {_safe(text[:200])}{'...' if len(text) > 200 else ''}")
        issues = scores.get("issues", [])
        if issues:
            print(f"    Issues: {[_safe(str(x)) for x in issues]}")
        if total > best_score:
            best_score = total
            best_text = text

    # Score with the comment_scorer
    time.sleep(API_DELAY)
    scorer_template = load_prompt("comment_scorer")
    scorer_filled = scorer_template.replace("{post_text}", SAMPLE_POST_1).replace("{candidates_json}", json.dumps(candidates))
    raw_score = call_groq("You are a comment quality evaluator. Return ONLY valid JSON.", scorer_filled, max_tokens=500)
    score_data = parse_json(raw_score)
    print(f"\n  Scorer winner_index: {score_data.get('winner_index', '?')}")
    for s in score_data.get("scores", []):
        print(f"    [{s.get('index','?')}] total={s.get('total',0)} reject={s.get('reject_reason','none')}")

    return candidates, {"best_score": best_score, "best_text": best_text}


def test_post():
    print("\n" + "=" * 70)
    print("TEST 3: POST GENERATION")
    print("=" * 70)
    template = load_prompt("post")
    filled = (template
        .replace("{topic}", "Why finance teams spend more time building reports than reading them")
        .replace("{style}", "Story")
        .replace("{tone}", "Conversational")
        .replace("{word_count}", "150"))

    system = "You are a LinkedIn content strategist. Write only the post text -- no title, no intro, no explanation."
    text = call_groq(system, filled, max_tokens=500)
    time.sleep(API_DELAY)
    scores = score_text(text, "LinkedIn post")
    print_result("POST", text, scores, 1)

    best_text, best_scores = text, scores
    for round_num in range(2, MAX_ROUNDS + 1):
        if best_scores.get("total", 0) >= PASS_SCORE:
            print(f"  [OK] Passed on round {round_num - 1}")
            break
        issues = scores.get("issues", ["Generic or AI-sounding"])
        print(f"\n  Refining (round {round_num})...")
        text = refine_text(text, issues, "LinkedIn post",
                          "Topic: Why finance teams spend more time building reports than reading them\nStyle: Story\nTone: Conversational")
        time.sleep(API_DELAY)
        scores = score_text(text, "LinkedIn post")
        print_result("POST", text, scores, round_num)
        if scores.get("total", 0) > best_scores.get("total", 0):
            best_text, best_scores = text, scores

    return best_text, best_scores


def test_note():
    print("\n" + "=" * 70)
    print("TEST 4: CONNECTION NOTE")
    print("=" * 70)
    template = load_prompt("note")
    filled = (template
        .replace("{first_name}", "Marcus")
        .replace("{title}", "Director of Analytics")
        .replace("{company}", "Schneider Electric")
        .replace("{shared_context}", "His post about building KPI frameworks from scratch at a manufacturing company")
        .replace("{topics}", TOPICS))

    system = "You are writing a LinkedIn connection request note. Write only the note text -- no intro, no quotes, no explanation."
    text = call_groq(system, filled, max_tokens=200, temperature=0.7)
    # Strip any surrounding quotes the model might add
    text = text.strip().strip('"\'')
    char_count = len(text)
    time.sleep(API_DELAY)
    scores = score_text(text, "connection note")
    print_result("NOTE", text, scores, 1)
    print(f"  Character count: {char_count}/300")

    best_text, best_scores, best_chars = text, scores, char_count
    for round_num in range(2, MAX_ROUNDS + 1):
        if best_scores.get("total", 0) >= PASS_SCORE and best_chars <= 300:
            print(f"  [OK] Passed on round {round_num - 1}")
            break
        issues = scores.get("issues", [])
        if char_count > 300:
            issues.append(f"Too long: {char_count} chars, must be under 300")
        print(f"\n  Refining (round {round_num})...")
        text = refine_text(text, issues, "connection note",
                          "Target: Marcus, Director of Analytics at Schneider Electric\nContext: KPI frameworks for manufacturing\nHARD LIMIT: 300 characters\nDo NOT use: resonates, I'd love to, would love to, game-changer, synergy, aligns with")
        text = text.strip().strip('"\'')
        char_count = len(text)
        time.sleep(API_DELAY)
        scores = score_text(text, "connection note")
        print_result("NOTE", text, scores, round_num)
        print(f"  Character count: {char_count}/300")
        if scores.get("total", 0) > best_scores.get("total", 0) and char_count <= 300:
            best_text, best_scores, best_chars = text, scores, char_count

    return best_text, best_scores


def test_reply():
    print("\n" + "=" * 70)
    print("TEST 5: REPLY GENERATION")
    print("=" * 70)
    template = load_prompt("reply")
    filled = (template
        .replace("{original_post}", SAMPLE_POST_3)
        .replace("{your_comment}", "The harder problem is even knowing which metric to prioritize. I watched a logistics company spend 6 months tracking shipment counts before realizing on-time delivery rate was the only number the CEO actually cared about.")
        .replace("{replier_name}", "Priya")
        .replace("{reply_to_comment}", "Exactly this. We spent a year building a beautiful Tableau dashboard around delivery volume. Nobody opened it once we launched. The actual decision was always about delivery reliability."))

    system = "You are continuing a LinkedIn comment thread conversation. Write only the reply text."
    text = call_groq(system, filled, max_tokens=200, temperature=0.8)
    time.sleep(API_DELAY)
    scores = score_text(text, "LinkedIn reply")
    print_result("REPLY", text, scores, 1)

    best_text, best_scores = text, scores
    for round_num in range(2, MAX_ROUNDS + 1):
        if best_scores.get("total", 0) >= PASS_SCORE:
            print(f"  [OK] Passed on round {round_num - 1}")
            break
        issues = scores.get("issues", ["Generic opener"])
        print(f"\n  Refining (round {round_num})...")
        text = refine_text(text, issues, "LinkedIn reply",
                          "This is a reply to Priya who said their Tableau dashboard on delivery volume was never opened because the real decision was about delivery reliability.")
        time.sleep(API_DELAY)
        scores = score_text(text, "LinkedIn reply")
        print_result("REPLY", text, scores, round_num)
        if scores.get("total", 0) > best_scores.get("total", 0):
            best_text, best_scores = text, scores

    return best_text, best_scores


def test_relevance():
    print("\n" + "=" * 70)
    print("TEST 6: RELEVANCE SCORING")
    print("=" * 70)

    test_cases = [
        {
            "label": "High-relevance (BI story)",
            "post": "Spent 3 years as a data analyst building Power BI reports for a retail chain. Last week I finally got a thank you from the CFO not for the beautiful charts but for saving her 2 hours every Monday. Turns out the metric she needed was buried in slide 12 of a 40-page report. Moved it to a single-number tile on the homepage. That was it.",
            "author": "Chen Wei",
            "expected_min": 8,
        },
        {
            "label": "Low-relevance (job announcement)",
            "post": "Thrilled to announce I've joined DataCorp as their new Head of Analytics! Excited for this new chapter.",
            "author": "Alex Johnson",
            "expected_max": 1,
        },
        {
            "label": "Mid-relevance (generic advice)",
            "post": "Data quality is important for making good decisions. Always clean your data before analysis.",
            "author": "Sam Lee",
            "expected_range": (3, 6),
        },
    ]

    template = load_prompt("relevance")
    all_pass = True
    for case in test_cases:
        filled = (template
            .replace("{topics}", TOPICS)
            .replace("{author_name}", case["author"])
            .replace("{post_text}", case["post"]))
        time.sleep(API_DELAY + 3)
        raw = call_groq("You are a relevance scoring engine. Return ONLY valid JSON.", filled, max_tokens=200, temperature=0.2)
        data = parse_json(raw)
        score = data.get("score", -1)
        reason = data.get("reason", "")
        label = case["label"]

        passed = True
        if "expected_min" in case and score < case["expected_min"]:
            passed = False
        if "expected_max" in case and score > case["expected_max"]:
            passed = False
        if "expected_range" in case:
            lo, hi = case["expected_range"]
            if not (lo <= score <= hi):
                passed = False

        status = "PASS" if passed else "FAIL"
        all_pass = all_pass and passed
        print(f"\n  [{status}] {label}")
        print(f"    Score: {score}/10 — {reason}")
        if not passed:
            expected = case.get("expected_min", case.get("expected_max", case.get("expected_range")))
            print(f"    Expected: {expected}")

    return all_pass


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "#" * 70)
    print("  BLOGPILOT PROMPT QUALITY TEST — Self-Improving Loop")
    print(f"  Model: {MODEL}")
    print(f"  Pass threshold: {PASS_SCORE}/10  |  Max iterations: {MAX_ROUNDS}")
    print("#" * 70)

    results = {}

    try:
        comment_text, comment_scores = test_comment()
        results["comment"] = comment_scores.get("total", 0)
    except Exception as e:
        print(f"\n  ERROR in comment test: {e}")
        results["comment"] = 0

    time.sleep(5)

    try:
        candidates, cand_scores = test_comment_candidates()
        results["comment_candidates"] = cand_scores.get("best_score", 0)
    except Exception as e:
        print(f"\n  ERROR in comment candidates test: {e}")
        results["comment_candidates"] = 0

    time.sleep(5)

    try:
        post_text, post_scores = test_post()
        results["post"] = post_scores.get("total", 0)
    except Exception as e:
        print(f"\n  ERROR in post test: {e}")
        results["post"] = 0

    time.sleep(5)

    try:
        note_text, note_scores = test_note()
        results["note"] = note_scores.get("total", 0)
    except Exception as e:
        print(f"\n  ERROR in note test: {e}")
        results["note"] = 0

    time.sleep(5)

    try:
        reply_text, reply_scores = test_reply()
        results["reply"] = reply_scores.get("total", 0)
    except Exception as e:
        print(f"\n  ERROR in reply test: {e}")
        results["reply"] = 0

    time.sleep(5)

    try:
        relevance_pass = test_relevance()
        results["relevance"] = 10 if relevance_pass else 5
    except Exception as e:
        print(f"\n  ERROR in relevance test: {e}")
        results["relevance"] = 0

    # Summary
    print("\n" + "=" * 70)
    print("  FINAL RESULTS SUMMARY")
    print("=" * 70)
    passed = 0
    total_tests = len(results)
    for name, score in results.items():
        status = "PASS" if score >= PASS_SCORE else "FAIL"
        bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"  {name:<25} {bar} {score:5.1f}/10  [{status}]")
        if score >= PASS_SCORE:
            passed += 1

    print(f"\n  Passed: {passed}/{total_tests}")
    if passed == total_tests:
        print("  All prompts producing human-quality output.")
    else:
        failed = [n for n, s in results.items() if s < PASS_SCORE]
        print(f"  Still needs work: {', '.join(failed)}")
    print("")

    return 0 if passed >= total_tests * 0.8 else 1


if __name__ == "__main__":
    sys.exit(main())
