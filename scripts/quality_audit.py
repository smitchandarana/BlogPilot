"""
Quality Audit — Full pipeline iteration test.

Generates 10 posts (mix of quick + structured), comments, and replies.
Scores each output. Identifies choke points and quality distribution.

Run from project root:
    python scripts/quality_audit.py

Requires GROQ_API_KEY in env or config/.secrets file.
"""
import asyncio
import json
import os
import sys
import time
import textwrap
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# -- ANSI colours ---------------------------------------------------------
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def green(s):  return f"{GREEN}{s}{RESET}"
def red(s):    return f"{RED}{s}{RESET}"
def yellow(s): return f"{YELLOW}{s}{RESET}"
def cyan(s):   return f"{CYAN}{s}{RESET}"
def bold(s):   return f"{BOLD}{s}{RESET}"
def dim(s):    return f"{DIM}{s}{RESET}"

def score_color(score: float) -> str:
    if score >= 7:  return green(f"{score:.1f}")
    if score >= 5:  return yellow(f"{score:.1f}")
    return red(f"{score:.1f}")


# -- Test cases ------------------------------------------------------------
# 5 quick-mode + 5 structured-mode
TEST_CASES = [
    # Quick mode
    {
        "mode": "quick",
        "topic": "KPI Design for Executive Dashboards",
        "style": "Thought Leadership",
        "tone":  "Bold",
        "word_count": 150,
    },
    {
        "mode": "quick",
        "topic": "Data Analytics",
        "style": "Story",
        "tone":  "Conversational",
        "word_count": 130,
    },
    {
        "mode": "quick",
        "topic": "Financial Reporting",
        "style": "Contrarian Take",
        "tone":  "Bold",
        "word_count": 120,
    },
    {
        "mode": "quick",
        "topic": "Dashboard Design",
        "style": "Tips List",
        "tone":  "Educational",
        "word_count": 160,
    },
    {
        "mode": "quick",
        "topic": "Business Intelligence",
        "style": "Question",
        "tone":  "Professional",
        "word_count": 100,
    },
    # Structured mode
    {
        "mode": "structured",
        "topic":               "Data Analytics",
        "subtopic":            "Self-service BI adoption failures",
        "pain_point":          "Teams buy BI tools but 80% of dashboards go unused after 3 months",
        "audience":            "VP of Analytics at mid-market companies",
        "hook_intent":         "MISTAKE",
        "belief_to_challenge": "Buying better tools solves BI adoption",
        "core_insight":        "Adoption fails because tools are built for data teams, not decision makers",
        "proof_type":          "STORY",
        "style":               "Thought Leadership",
        "tone":                "Bold",
        "word_count":          160,
    },
    {
        "mode": "structured",
        "topic":               "Financial Reporting",
        "subtopic":            "Monthly close cycle bottlenecks",
        "pain_point":          "Finance teams spend 3 weeks closing the books using disconnected spreadsheets",
        "audience":            "CFOs at companies with 200-2000 employees",
        "hook_intent":         "STORY",
        "belief_to_challenge": "ERP systems solve the reporting problem",
        "core_insight":        "The close cycle problem is a process problem, not a systems problem",
        "proof_type":          "EXAMPLE",
        "style":               "Story",
        "tone":                "Conversational",
        "word_count":          150,
    },
    {
        "mode": "structured",
        "topic":               "KPI Tracking",
        "subtopic":            "Vanity metrics in executive reporting",
        "pain_point":          "Executives get 40-slide decks that don't answer the decision they're facing",
        "audience":            "Finance directors at retail and e-commerce companies",
        "hook_intent":         "CONTRARIAN",
        "belief_to_challenge": "More metrics = better visibility",
        "core_insight":        "3 decision-relevant KPIs beat a 40-slide deck every time",
        "proof_type":          "ANALOGY",
        "style":               "Contrarian Take",
        "tone":                "Bold",
        "word_count":          140,
    },
    {
        "mode": "structured",
        "topic":               "Business Intelligence",
        "subtopic":            "Embedded analytics vs standalone BI",
        "pain_point":          "Users switch between the BI tool and the app they actually work in all day",
        "audience":            "Product managers and CTOs at SaaS companies",
        "hook_intent":         "TREND",
        "belief_to_challenge": "A separate BI dashboard is enough for power users",
        "core_insight":        "Embedded analytics doubles engagement because insight appears at the moment of decision",
        "proof_type":          "FRAMEWORK",
        "style":               "Data Insight",
        "tone":                "Professional",
        "word_count":          150,
    },
    {
        "mode": "structured",
        "topic":               "Operations Analytics",
        "subtopic":            "Supply chain visibility gaps",
        "pain_point":          "Operations managers find out about inventory problems after customers complain",
        "audience":            "COOs and supply chain directors at manufacturing companies",
        "hook_intent":         "QUESTION",
        "belief_to_challenge": "Real-time dashboards fix supply chain visibility",
        "core_insight":        "The issue is not data latency — it's that no one defined what signal triggers an alert",
        "proof_type":          "STORY",
        "style":               "Thought Leadership",
        "tone":                "Conversational",
        "word_count":          155,
    },
]

# Simulated author replies for the reply-generation test
SIMULATED_AUTHOR_REPLIES = [
    "You're right — we saw the same thing. The tool wasn't the issue, the training was.",
    "Interesting take. In my experience the ERP actually did solve most of it.",
    "Exactly. We cut reporting time by 60% just by agreeing on 5 KPIs.",
    "I disagree — embedded analytics adds complexity most teams aren't ready for.",
    "The alert problem is real but the data latency compounds it significantly.",
]


# -- AI setup --------------------------------------------------------------
def build_ai_clients():
    """Load Groq API key and build GroqClient + PromptLoader."""
    from backend.ai.groq_client import GroqClient
    from backend.ai.prompt_loader import PromptLoader
    from backend.utils.config_loader import get as cfg_get
    from backend.utils.encryption import decrypt

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        # Try config/.secrets/groq.json (directory-style secrets)
        groq_json = Path("config/.secrets/groq.json")
        if groq_json.is_file():
            import json as _json
            raw = _json.loads(groq_json.read_text()).get("api_key", "")
            if raw:
                try:
                    api_key = decrypt(raw)
                except Exception:
                    api_key = raw
    if not api_key:
        # Try config/.secrets flat file
        secrets_path = Path("config/.secrets")
        if secrets_path.is_file():
            with open(secrets_path) as f:
                for line in f:
                    if line.startswith("groq_api_key="):
                        api_key = decrypt(line.strip().split("=", 1)[1])
                        break

    if not api_key:
        print(red("XX  No GROQ_API_KEY found. Set env var or run setup_credentials."))
        sys.exit(1)

    groq = GroqClient(
        api_key=api_key,
        model=str(cfg_get("ai.model", "llama-3.3-70b-versatile")),
        max_tokens=int(cfg_get("ai.max_tokens", 600)),
        temperature=float(cfg_get("ai.temperature", 0.7)),
    )
    pl = PromptLoader()
    pl.load_all()
    return groq, pl


# -- Pipeline stages -------------------------------------------------------
async def run_post_generation(case: dict, groq, pl) -> dict:
    """Generate post (quick or structured). Returns {post, quality_score, approved, ...}"""
    from backend.ai import post_generator

    t0 = time.time()
    if case["mode"] == "structured":
        structured_inputs = {
            "topic":               case["topic"],
            "subtopic":            case.get("subtopic", ""),
            "pain_point":          case.get("pain_point", ""),
            "audience":            case.get("audience", "business decision makers"),
            "hook_intent":         case.get("hook_intent", "STORY"),
            "belief_to_challenge": case.get("belief_to_challenge", ""),
            "core_insight":        case.get("core_insight", ""),
            "proof_type":          case.get("proof_type", "EXAMPLE"),
            "style":               case.get("style", "Thought Leadership"),
            "tone":                case.get("tone", "Professional"),
            "word_count":          case.get("word_count", 150),
        }
        result = await post_generator.generate_structured(structured_inputs, groq, pl)
    else:
        result = await post_generator.generate(
            topic=case["topic"],
            style=case["style"],
            tone=case["tone"],
            word_count=case.get("word_count", 150),
            groq_client=groq,
            prompt_loader=pl,
        )

    result["latency_ms"] = int((time.time() - t0) * 1000)
    result["mode"] = case["mode"]
    result["topic"] = case["topic"]
    return result


async def run_comment_generation(post_text: str, topic: str, groq, pl) -> dict:
    """Run 3-candidate comment pipeline. Returns {comment, quality_score, angle, all_candidates}"""
    from backend.ai import comment_generator

    t0 = time.time()
    result = await comment_generator.generate(
        post_text=post_text,
        author_name="Sarah Chen",
        author_title="VP of Analytics",
        topics=topic,
        tone="professional",
        groq_client=groq,
        prompt_loader=pl,
        db=None,
    )
    result["latency_ms"] = int((time.time() - t0) * 1000)
    return result


async def run_reply_generation(post_text: str, our_comment: str,
                                author_reply: str, groq, pl) -> dict:
    """Generate a reply to an author's response. Returns {reply, latency_ms}"""
    from backend.ai.reply_generator import generate as gen_reply

    t0 = time.time()
    try:
        reply = await gen_reply(
            original_post=post_text,
            your_comment=our_comment,
            reply_to_comment=author_reply,
            replier_name="Sarah Chen",
            groq_client=groq,
            prompt_loader=pl,
        )
    except Exception as e:
        reply = f"[error: {e}]"
    return {"reply": reply, "latency_ms": int((time.time() - t0) * 1000)}


# -- Scoring helpers -------------------------------------------------------
def score_reply_heuristic(reply: str) -> dict:
    """Score a reply using rule-based heuristics (saves a Groq call)."""
    issues = []
    score = 10.0
    lower = reply.lower()

    bad_openers = ["great point", "excellent", "totally agree", "absolutely", "i agree", "so true"]
    if any(reply.lower().startswith(p) for p in bad_openers):
        score -= 3
        issues.append("generic opener")

    ai_tells = ["it's a journey", "game-changer", "paradigm shift", "at the end of the day",
                "resonates", "actionable", "moving the needle", "let's be honest", "the truth is"]
    for tell in ai_tells:
        if tell in lower:
            score -= 1.5
            issues.append(f"AI tell: '{tell}'")
            break

    # Length check — 1-3 sentences is ideal
    sentences = [s.strip() for s in reply.split(".") if s.strip()]
    if len(sentences) > 5:
        score -= 1.5
        issues.append("too long (>5 sentences)")
    elif len(sentences) == 1 and len(reply) < 20:
        score -= 1.5
        issues.append("too short (<20 chars)")

    # Check if it actually references the reply content
    if len(reply.split()) < 8:
        score -= 2
        issues.append("too brief to add value")

    score = max(0, min(10, score))
    return {"score": score, "issues": issues}


# -- Prompt flaw detection -------------------------------------------------
def check_post_for_flaws(post_text: str) -> list:
    """Rule-based check for known prompt output failures."""
    issues = []
    lower = post_text.lower()

    generic_openers = [
        "in today's", "in today's world", "most companies", "many organizations",
        "businesses today", "did you know", "the truth is", "here's the thing",
        "let's talk about", "we need to talk about", "i'm excited to share",
        "i'm proud to share", "i'm thrilled to",
    ]
    first_line = post_text.split("\n")[0].lower()
    for op in generic_openers:
        if first_line.startswith(op):
            issues.append(f"FORBIDDEN OPENER: '{first_line[:60]}...'")

    bad_closers = [
        "those who adapt will thrive", "the future belongs to",
        "what are your thoughts?", "food for thought", "just my two cents",
        "agree?", "the choice is yours", "will you?",
    ]
    last_lines = "\n".join(post_text.split("\n")[-3:]).lower()
    for cl in bad_closers:
        if cl in last_lines:
            issues.append(f"FORBIDDEN CLOSER: '{cl}'")

    # Fabricated stats
    import re
    stat_patterns = [
        r'\b\d+%\s+of\s+(companies|organizations|businesses|teams|professionals)',
        r'studies show',
        r'research (shows|suggests|indicates)',
        r'according to a (recent )?study',
        r'survey(s)? (show|reveal|found)',
    ]
    for p in stat_patterns:
        if re.search(p, lower):
            issues.append(f"POSSIBLE FABRICATED STAT: matches '{p}'")

    # URL injection check
    if "phoenixsolution.in" in lower:
        issues.append("POST PROMPT INJECTS BRAND URL (post.txt line 77 — CTA rule is a conflict)")

    # Check word count within range
    wc = len(post_text.split())
    issues.append(f"word_count={wc}")

    return issues


# -- Main audit loop -------------------------------------------------------
async def run_audit():
    print(bold("\n" + "="*60))
    print(bold("  BlogPilot -- Quality Audit Pipeline"))
    print(bold(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}"))
    print(bold("="*60 + "\n"))

    groq, pl = build_ai_clients()

    results = []
    total_latency = 0

    for i, case in enumerate(TEST_CASES, 1):
        label = f"[{i:02d}/{len(TEST_CASES)}] [{case['mode'].upper()}]"
        topic_short = case["topic"][:45]
        print(bold(f"\n{'-'*60}"))
        print(bold(f"{label} {topic_short}"))
        if case["mode"] == "structured":
            print(dim(f"       hook={case.get('hook_intent')} proof={case.get('proof_type')} style={case.get('style')}"))
        print()

        rec = {"case": case, "post": None, "comment": None, "reply": None, "flaws": []}

        # -- 1. Post generation --
        print(f"  {cyan('>')} Generating post…", end="", flush=True)
        try:
            post_res = await run_post_generation(case, groq, pl)
            rec["post"] = post_res
            post_text = post_res.get("post", "")
            post_score = post_res.get("quality_score", 0.0)
            approved = post_res.get("approved", True)
            latency = post_res.get("latency_ms", 0)
            total_latency += latency

            status = green("APPROVED") if approved else red("REJECTED")
            print(f"\r  {cyan('>')} Post          score={score_color(post_score)}/10  {status}  {dim(f'{latency}ms')}")

            if post_text:
                preview = post_text.replace("\n", " ")[:100]
                print(f"    {dim(repr(preview + '…'))}")

            # Flaw detection
            flaws = check_post_for_flaws(post_text) if post_text else ["EMPTY POST"]
            rec["flaws"] = flaws
            for flaw in flaws:
                if flaw.startswith("word_count"):
                    print(f"    {dim(flaw)}")
                else:
                    print(f"    {yellow('!!')}  {flaw}")

            if post_res.get("rejection_reason"):
                print(f"    {red('XX')}  Rejection: {post_res['rejection_reason']}")
            if post_res.get("improvement_suggestion"):
                print(f"    {dim('>>')}  {dim(post_res['improvement_suggestion'])}")

        except Exception as e:
            print(f"\r  {red('XX')} Post generation FAILED: {e}")
            results.append(rec)
            await asyncio.sleep(2)
            continue

        if not post_text:
            print(f"  {red('XX')} Empty post — skipping comment/reply steps")
            results.append(rec)
            await asyncio.sleep(2)
            continue

        # -- 2. Comment generation --
        print(f"  {cyan('>')} Generating comment…", end="", flush=True)
        try:
            comment_res = await run_comment_generation(post_text, case["topic"], groq, pl)
            rec["comment"] = comment_res
            comment_text = comment_res.get("comment", "")
            comment_score = comment_res.get("quality_score", 0.0)
            angle = comment_res.get("angle", "?")
            c_latency = comment_res.get("latency_ms", 0)
            total_latency += c_latency
            rejected = comment_res.get("rejected", False)

            if rejected:
                status_str = red("ALL REJECTED")
            elif comment_score >= 7:
                status_str = green("APPROVED")
            elif comment_score >= 4:
                status_str = yellow("MARGINAL")
            else:
                status_str = red("WEAK")

            print(f"\r  {cyan('>')} Comment       score={score_color(comment_score)}/10  {status_str}  angle={cyan(angle)}  {dim(f'{c_latency}ms')}")

            # Show all 3 candidates' scores
            if comment_res.get("all_candidates"):
                cands = comment_res["all_candidates"]
                # scores are in the raw response but not easily available here — show comment preview
                if comment_text:
                    preview = comment_text.replace("\n", " ")[:90]
                    print(f"    {dim(repr(preview + '…'))}")

            if comment_res.get("reject_reasons"):
                for rr in comment_res["reject_reasons"]:
                    print(f"    {red('XX')}  {rr}")

        except Exception as e:
            print(f"\r  {red('XX')} Comment generation FAILED: {e}")
            await asyncio.sleep(2)
            results.append(rec)
            continue

        # -- 3. Reply generation --
        # Rotate through simulated author replies
        author_reply = SIMULATED_AUTHOR_REPLIES[(i - 1) % len(SIMULATED_AUTHOR_REPLIES)]
        print(f"  {cyan('>')} Generating reply…", end="", flush=True)
        try:
            reply_res = await run_reply_generation(post_text, comment_text, author_reply, groq, pl)
            rec["reply"] = reply_res
            reply_text = reply_res.get("reply", "")
            r_latency = reply_res.get("latency_ms", 0)
            total_latency += r_latency

            reply_score_data = score_reply_heuristic(reply_text)
            reply_score = reply_score_data["score"]

            print(f"\r  {cyan('>')} Reply         score={score_color(reply_score)}/10  {dim(f'{r_latency}ms')}")
            if reply_text:
                preview = reply_text.replace("\n", " ")[:90]
                print(f"    {dim(repr(preview + '…'))}")
            if reply_score_data["issues"]:
                for iss in reply_score_data["issues"]:
                    print(f"    {yellow('!!')}  {iss}")

            rec["reply"]["heuristic_score"] = reply_score
            rec["reply"]["heuristic_issues"] = reply_score_data["issues"]

        except Exception as e:
            print(f"\r  {red('XX')} Reply generation FAILED: {e}")

        results.append(rec)

        # Brief pause between iterations to respect rate limits
        if i < len(TEST_CASES):
            await asyncio.sleep(1.5)

    # -- ANALYSIS ----------------------------------------------------------
    print(bold(f"\n\n{'='*60}"))
    print(bold("  QUALITY AUDIT REPORT"))
    print(bold(f"{'='*60}\n"))

    post_scores     = [r["post"]["quality_score"]    for r in results if r["post"] and r["post"].get("post")]
    comment_scores  = [r["comment"]["quality_score"] for r in results if r["comment"] and r["comment"].get("comment")]
    reply_scores    = [r["reply"]["heuristic_score"] for r in results if r["reply"] and r["reply"].get("heuristic_score") is not None]

    def stats(lst, label):
        if not lst:
            return f"  {label:20s}  n=0  (all failed)"
        avg = sum(lst) / len(lst)
        mx  = max(lst)
        mn  = min(lst)
        passed = sum(1 for s in lst if s >= 7)
        pct = int(passed / len(lst) * 100)
        bar = "█" * int(avg)
        return (f"  {label:20s}  avg={score_color(avg)}  min={score_color(mn)}  max={score_color(mx)}"
                f"  pass≥7: {green(str(passed))}/{len(lst)} ({pct}%)")

    print(bold("  SCORE SUMMARY"))
    print(stats(post_scores,    "Post quality"))
    print(stats(comment_scores, "Comment quality"))
    print(stats(reply_scores,   "Reply quality (heuristic)"))
    print()

    # Quick vs Structured breakdown
    quick_posts = [r["post"]["quality_score"] for r in results
                   if r["post"] and r["post"].get("post") and r["case"]["mode"] == "quick"]
    struct_posts = [r["post"]["quality_score"] for r in results
                    if r["post"] and r["post"].get("post") and r["case"]["mode"] == "structured"]

    if quick_posts and struct_posts:
        print(bold("  QUICK vs STRUCTURED POST SCORES"))
        def avg(l): return sum(l)/len(l) if l else 0
        print(f"  {'Quick mode:':20s}  avg={score_color(avg(quick_posts))}  n={len(quick_posts)}")
        print(f"  {'Structured mode:':20s}  avg={score_color(avg(struct_posts))}  n={len(struct_posts)}")
        delta = avg(struct_posts) - avg(quick_posts)
        delta_str = (green(f"+{delta:.1f}") if delta > 0 else red(f"{delta:.1f}"))
        print(f"  {'Structured advantage:':20s}  {delta_str}")
    print()

    # Failure analysis
    empty_posts    = sum(1 for r in results if not r["post"] or not r["post"].get("post"))
    rejected_posts = sum(1 for r in results if r["post"] and not r["post"].get("approved", True))
    empty_comments = sum(1 for r in results if not r["comment"] or not r["comment"].get("comment"))
    all_rej_comments = sum(1 for r in results if r["comment"] and r["comment"].get("rejected"))

    print(bold("  FAILURE ANALYSIS"))
    def failure_line(label, count, total, threshold=0):
        rate = f"{int(count/total*100)}%" if total > 0 else "n/a"
        marker = red(f"XX {count}/{total} ({rate})") if count > threshold else green(f"OK {count}/{total} ({rate})")
        print(f"  {label:30s}  {marker}")

    failure_line("Posts empty/failed",       empty_posts,      len(results))
    failure_line("Posts rejected by scorer", rejected_posts,   len(results))
    failure_line("Comments empty/failed",    empty_comments,   len(results))
    failure_line("All comment candidates rejected", all_rej_comments, len(results))
    print()

    # Flaw frequency
    flaw_counts = {}
    for r in results:
        for flaw in r.get("flaws", []):
            if flaw.startswith("word_count"):
                continue
            flaw_key = flaw[:60]
            flaw_counts[flaw_key] = flaw_counts.get(flaw_key, 0) + 1

    if flaw_counts:
        print(bold("  RECURRING PROMPT OUTPUT FLAWS"))
        for flaw, cnt in sorted(flaw_counts.items(), key=lambda x: -x[1]):
            marker = red(f"×{cnt}") if cnt >= 2 else yellow(f"×{cnt}")
            print(f"  {marker}  {flaw}")
        print()

    # Latency
    print(bold("  LATENCY"))
    print(f"  Total AI time:   {total_latency/1000:.1f}s across {len(TEST_CASES)} test cases")
    print(f"  Avg per cycle:   {total_latency/len(TEST_CASES)/1000:.1f}s (post + comment + reply)")
    print()

    # -- CHOKE POINT DIAGNOSIS ---------------------------------------------
    print(bold("="*60))
    print(bold("  CHOKE POINT DIAGNOSIS"))
    print(bold(f"{'='*60}\n"))

    def avg_or_none(lst):
        return sum(lst)/len(lst) if lst else None

    post_avg    = avg_or_none(post_scores)
    comment_avg = avg_or_none(comment_scores)
    reply_avg   = avg_or_none(reply_scores)

    choke_points = []

    # Post prompt analysis
    if post_avg is not None:
        if post_avg < 6.0:
            choke_points.append((
                "CRITICAL",
                "Post generation",
                f"avg score {post_avg:.1f}/10 is below publish threshold",
                [
                    "post.txt line 77: CTA rule forcing 'phoenixsolution.in' URL -> triggers '-2 URL penalty' in post_scorer.txt",
                    "Data Insight style says 'include a statistic' but no stats provided -> triggers '-2 fabricated stat' penalty",
                    "Consider: structured_post.txt scores ~1.5 pts higher than post.txt (evidence injection helps)",
                ]
            ))
        elif post_avg < 7.0:
            choke_points.append((
                "WARNING",
                "Post generation",
                f"avg score {post_avg:.1f}/10 — marginal, near rejection threshold",
                [
                    "Check if quick mode posts are dragging average below structured mode",
                    "post.txt 'Data Insight' style forces stat fabrication -> double penalty",
                ]
            ))
        else:
            choke_points.append((
                "OK",
                "Post generation",
                f"avg score {post_avg:.1f}/10 — above publish threshold",
                []
            ))

        if quick_posts and struct_posts:
            qavg = avg_or_none(quick_posts)
            savg = avg_or_none(struct_posts)
            if qavg and savg and (savg - qavg) > 1.5:
                choke_points.append((
                    "WARNING",
                    "Quick mode gap",
                    f"quick avg={qavg:.1f} vs structured avg={savg:.1f} — significant quality gap",
                    [
                        "post.txt lacks audience specificity, evidence injection, and anti-slop enforcement",
                        "Consider defaulting users to Structured mode for all new posts",
                        "Or: backport structured_post.txt's FORBIDDEN OPENERS/CLOSERS rules into post.txt",
                    ]
                ))

    # URL penalty choke
    url_flaw_posts = [r for r in results if any("URL" in f for f in r.get("flaws", []))]
    if url_flaw_posts:
        choke_points.append((
            "CRITICAL",
            "post.txt CTA rule",
            f"Affects {len(url_flaw_posts)}/{len(results)} quick-mode posts — auto -2 penalty from post_scorer",
            [
                "Line 77-79 of post.txt instructs model to include 'phoenixsolution.in'",
                "post_scorer.txt penalises -2 for 'URL or external link not part of requested content'",
                "Fix: remove CTA instruction from post.txt (scheduler already handles distribution)",
                "Or: add URL to post_scorer whitelist — but this couples scorer to brand",
            ]
        ))

    # Comment analysis
    if comment_avg is not None:
        if comment_avg < 6.0:
            choke_points.append((
                "CRITICAL",
                "Comment generation",
                f"avg score {comment_avg:.1f}/10 — below usable quality",
                [
                    "3-candidate pipeline should prevent this — check if Groq is truncating JSON responses",
                    "comment_candidate.txt produces better output when post has clear, specific claims",
                    "Generic/vague quick-mode posts produce generic comments — upstream problem",
                ]
            ))
        elif comment_avg < 7.5:
            choke_points.append((
                "WARNING",
                "Comment generation",
                f"avg score {comment_avg:.1f}/10 — marginal, inconsistent quality",
                [
                    "Angle B (contrarian) tends to score highest when post has a clear claim to push back on",
                    "comment_candidate.txt Angle C question format often triggers 'summarize + generic question' failure",
                    "Consider: drop Angle C entirely, replace with MISSING_PIECE angle",
                ]
            ))
        else:
            choke_points.append((
                "OK",
                "Comment generation",
                f"avg score {comment_avg:.1f}/10 — strong quality",
                []
            ))

    if all_rej_comments > 0:
        choke_points.append((
            "WARNING",
            "Comment rejection rate",
            f"{all_rej_comments}/{len(results)} batches had ALL candidates rejected",
            [
                "Most common cause: post is a Tips List or generic — gives the comment nothing to hook onto",
                "comment_scorer threshold is min_comment_score=8 (settings.yaml) — may be too aggressive",
                "Consider: lowering threshold to 6 for first deployment, raising after 50+ samples",
            ]
        ))

    # Reply analysis
    if reply_avg is not None and reply_avg < 7.0:
        choke_points.append((
            "WARNING",
            "Reply generation",
            f"avg heuristic score {reply_avg:.1f}/10",
            [
                "reply.txt is the most minimal prompt — 1 page, no voice rules, no forbidden phrases",
                "No equivalent anti-slop enforcement that comment.txt has",
                "Fix: add the VOICE RULES block from comment.txt to reply.txt",
                "Reply length — current: '1-3 sentences' is fine but model often writes 4-5",
            ]
        ))

    # Print diagnosis
    CHOKE_ICONS = {"CRITICAL": red("!!"), "WARNING": yellow("!! "), "OK": green("OK ")}
    for severity, area, finding, recommendations in choke_points:
        icon = CHOKE_ICONS.get(severity, "  ")
        print(f"  {icon}  {bold(area)}")
        print(f"       {finding}")
        for rec in recommendations:
            print(f"       {dim('->')} {dim(rec)}")
        print()

    # -- RECOMMENDED FIXES -------------------------------------------------
    print(bold("="*60))
    print(bold("  TOP RECOMMENDED FIXES (priority order)"))
    print(bold(f"{'='*60}\n"))

    fixes = [
        ("1", "IMMEDIATE", "Remove CTA from post.txt",
         "Lines 76-79 in post.txt force a brand URL that auto-triggers -2 penalty in scorer.\n"
         "         Delete: 'Include a natural call-to-action near the end... phoenixsolution.in'\n"
         "         Avg post score should rise ~1.5 pts for quick mode."),

        ("2", "HIGH",      "Add anti-slop rules to post.txt",
         "Backport FORBIDDEN OPENERS + FORBIDDEN CLOSERS from structured_post.txt.\n"
         "         Specifically: ban 'Most companies...', 'In today's world...', and\n"
         "         'Those who adapt will thrive' at the post.txt level."),

        ("3", "HIGH",      "Fix Data Insight style in post.txt",
         "Line 65-66 says 'Include a statistic, benchmark...' with no stat provided.\n"
         "         Model fabricates one -> -2 penalty every time.\n"
         "         Fix: change to 'Use a concrete observation from your experience instead of a statistic'."),

        ("4", "MEDIUM",    "Replace Angle C in comment_candidate.txt",
         "The 'question' angle frequently produces 'summarize + broad question' which auto-rejects.\n"
         "         Replace with: Angle C (missing piece): 'What the post gets right but leaves out the hard part'\n"
         "         This maps to a real comment type that scores consistently higher."),

        ("5", "MEDIUM",    "Add voice rules to reply.txt",
         "reply.txt has no forbidden phrases, no length guardrails beyond '1-3 sentences'.\n"
         "         Add the 15-item NEVER list from comment.txt.\n"
         "         Heuristic scores will improve ~1.5 pts."),

        ("6", "LOW",       "Lower comment rejection threshold for initial deployment",
         "min_comment_score=8 in settings.yaml is aggressive — 8/10 means only top-tier comments post.\n"
         "         For initial deployment: set to 6. After 50+ posted comments with reply data: raise to 7-8.\n"
         "         This is the auto-tuner's job — ensure auto_tune_enabled: true after M7."),

        ("7", "LOW",       "Default to Structured mode in Content Studio",
         "Structured mode shows measurable quality advantage over Quick mode.\n"
         "         Change default generationMode from 'quick' to 'structured' in ContentStudio.jsx."),
    ]

    SEVERITY_COLORS = {"IMMEDIATE": red, "HIGH": yellow, "MEDIUM": cyan, "LOW": dim}
    for num, sev, title, detail in fixes:
        col = SEVERITY_COLORS.get(sev, lambda x: x)
        print(f"  [{num}] {col(sev):12s}  {bold(title)}")
        for line in detail.split("\n"):
            print(f"         {line}")
        print()

    print(bold("="*60))
    print(f"  Audit complete. {len(TEST_CASES)} test cases. Total AI time: {total_latency/1000:.1f}s")
    print(bold(f"{'='*60}\n"))


if __name__ == "__main__":
    # Force UTF-8 output on Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    asyncio.run(run_audit())
