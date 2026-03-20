# Content Studio

![Content Studio](temporary%20screenshots/screenshot-1-fullpage.png)

---

## What it is

Content Studio is the AI-powered post creation hub. It does two things:

1. **Research** — continuously scans the internet for trending topics in your niche
2. **Write** — generates LinkedIn posts grounded in that research, scored for quality before you see them

You never start from a blank page. Every post is backed by real signals from Reddit, RSS feeds, and Hacker News.

---

## Section 1 — Topic Research Panel

This is the top section of the page. It shows all research topics the engine has discovered, displayed as cards in a grid.

### How topics get here

The engine runs a research scan every 6 hours automatically. It:
1. Pulls posts from Reddit (subreddits: BusinessIntelligence, datascience, analytics, PowerBI, etc.), RSS feeds (Towards Data Science, Analytics Vidhya), and Hacker News
2. Filters results by your configured domain topics (Business Intelligence, Data Analytics, etc.)
3. Sends batches of snippets to Groq, which extracts specific subtopics (not just broad categories — e.g. "EDA", "KPI design", "Cohort analysis")
4. Deduplicates subtopics across sources
5. Scores each subtopic and stores it if it passes the quality gate (min score 4.0)

### What each topic card shows

| Field | What it means |
|---|---|
| Domain badge | The broad category it belongs to (e.g. "Data Visualization", "Power BI") |
| Topic name | The specific subtopic the AI extracted |
| Score dot | Green ≥ 7, amber ≥ 5, red < 5 |
| Source count | How many articles/posts were used to identify this topic |
| **Trending** bar | How much online buzz this topic has right now |
| **Engage** bar | Engagement signal from the source material |
| **Gap** bar | How underserved this topic is on LinkedIn (high gap = opportunity) |
| **Relevant** bar | Match score against your configured target topics |
| Suggested angle | AI-generated writing angle for that topic (italic lightbulb hint) |

### Buttons on each card

- **Generate Post** — sends that topic to the generator below; switches to Structured mode and fills fields from the research
- **Sources** — expands to show the raw research snippets used. Each snippet shows: source platform (Reddit/RSS/HN/LinkedIn), engagement signal, article title, and a link to the original
- **× (dismiss)** — removes the topic card from view (does not delete from DB)

### Panel controls

- **Run Research** — manually triggers a scan right now (normally runs every 6h)
- **Clear All** — wipes all researched topics from the database. Use when you want a completely fresh set

---

## Section 2 — Post Generator

Below the research panel. This is where you write and publish posts.

### Two generation modes

Toggle between **Quick** and **Structured** at the top of the generator.

---

### Quick Mode

Simple inputs, fast output. Use when you want a post on a topic without deep control.

| Input | Options |
|---|---|
| Topic | Dropdown of your configured topics + any custom input |
| Style | Thought Leadership / Story / Tips List / Question / Data Insight / Contrarian Take |
| Tone | Professional / Conversational / Bold / Educational |
| Word Count | Slider, approximately 80–300 words |

Click **Generate** → Groq writes the post → a second AI call scores it for quality → if it passes (score ≥ 7/10), the post appears in the output area.

---

### Structured Mode

More control. You define the exact argumentative shape of the post before the AI writes it. Produces higher-quality, more specific output.

| Field | What it controls |
|---|---|
| **Subtopic** | The narrow angle within the broader topic |
| **Target Audience** | Who this post is written for (e.g. "CFOs at manufacturing firms") |
| **Pain Point** | The specific problem the audience has (fills the post's emotional hook) |
| **Hook Intent** | How the post opens — see hook types below |
| **Belief to Challenge** | A common assumption you want to contradict (used by Contrarian hook) |
| **Core Insight** | The main point or data fact the post is built around |
| **Proof Type** | How the insight is demonstrated: Statistic / Story / Example / Analogy / Framework |
| Style, Tone, Word Count | Same as Quick mode |

#### Hook types

| Hook | What it does |
|---|---|
| **Contrarian** | Opens by quoting the conventional wisdom, then destroys it with one concrete specific |
| **Question** | Opens with a question the audience is already asking privately — must be answerable, not rhetorical |
| **Statistic** | Opens with a surprising number. If no real stat is provided, the AI automatically switches to Story — it will not fabricate statistics |
| **Story** | Drops into a specific scene. First sentence names a role and creates a moment the audience recognises |
| **Trend** | Uses a before/after frame. Names the exact thing that changed, not just "things are changing" |
| **Mistake** | States the error in the first sentence: [role] does [action] when [situation], then shows the specific cost |

---

### Intelligence Panel (Structured mode only)

Appears inside the Structured form. Shows AI-extracted patterns from your content intelligence library — things the research engine has learned are high-signal across many sources.

Three sections, each clickable to auto-fill the corresponding form field:

- **Top Pain Points** — the most-cited audience problems, with occurrence count and ✦ drilldown
- **Hook Types** — which opening styles appear most in high-engagement content for this topic
- **Audience Segments** — specific audience types that appear repeatedly in the research

Click any item → that field in the form is filled automatically.

Click **✦** on any item → opens the **Insight Drilldown Modal**:
- Shows every ContentInsight record that contributed to that pattern
- Each record: hook type, source platform, specificity score (0–10), the exact key insight, pain point, audience
- **"Use this insight"** button — fills ALL structured form fields at once from that single insight record

---

### "Write like my best posts" button

Available in Structured mode when you have published posts with session data.

What it does:
1. Fetches your top 3 published posts (ranked by quality score)
2. Injects their style, hook type, tone, and opening lines as a style reference into the next generate call
3. The AI uses them as a writing template — matching your voice, not a generic one

The style reference is used only once (cleared after generation).

---

### "Learn from Content" panel

Paste any existing LinkedIn post — your own, a competitor's, one you admire.

Click **Extract & Learn**:
1. AI extracts structured metadata: subtopic, pain point, hook type, content style, key insight, audience segment, sentiment, specificity score
2. Saves it as a ContentInsight record (source: MANUAL) to your intelligence library
3. Auto-fills the Structured form fields with the extracted values

Use this to teach the intelligence layer what good content looks like before you have enough published sessions to learn from.

---

## Section 3 — Post Output

After generation, the post appears in an editable textarea.

| Control | What it does |
|---|---|
| **Character counter** | Shows current / 3000 (LinkedIn's character limit) |
| **Copy** | Copies the post text to clipboard |
| **Regenerate** | Runs generation again with the same inputs |
| **Post Now** | Publishes immediately via the LinkedIn browser session. Engine must be RUNNING. Takes 10–30 seconds. |
| **Schedule** | Opens a date/time picker → adds to the publish queue |

### Quality gate

Every generated post is scored by a second Groq call before it reaches the output area. The scorer evaluates:
- Hook strength
- Specificity (no vague generalisations)
- Audience fit
- Structure and readability

Minimum passing score: **7/10** (configured in `settings.yaml → quality.min_post_score`).

If the post fails: the score, rejection reason, and an improvement suggestion are shown. You can regenerate or edit and proceed anyway.

---

## Section 4 — Duplicate Detection

Before any post is scheduled or published, the engine checks it against all posts already in the database.

If a near-duplicate is found:
- Shows similarity percentage and a preview of the matching post
- Blocks the action
- You can click **Force Post** to override and publish anyway

---

## Section 5 — Post Queue

Table at the bottom of the page showing all posts that have been scheduled or published.

| Column | Values |
|---|---|
| Scheduled time | When it is set to publish |
| Topic | The topic used |
| Style | The post style |
| Status | Scheduled (purple) / Published (green) / Failed (red) / Cancelled (grey) |

**Cancel** button appears on SCHEDULED posts only. Published and failed posts are read-only history.

The scheduler checks the queue every 1 minute. When a post's scheduled time arrives, the engine opens the LinkedIn browser session and publishes it automatically.

---

## How the AI learns over time

Every time you generate, publish, or schedule a post, the system logs a **GenerationSession** — recording the topic, hook type, style, tone, the generated text, how much you edited it, and the final action taken.

After 3 published sessions, the Intelligence Panel starts **auto-filling** your Structured form on page load with the hook types, audiences, and styles that have historically performed best for your account.

This gets better the more you use it.

---

## Research sources

| Source | What it scans |
|---|---|
| Reddit | BusinessIntelligence, datascience, analytics, PowerBI, dataengineering, tableau |
| RSS | Towards Data Science, Analytics Vidhya |
| Hacker News | Top stories (disabled by default, enable in settings) |
| LinkedIn | Feed insights (requires browser session) |

All sources are configurable in `config/settings.yaml → research`.
