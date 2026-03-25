# Ideas Lab — Design Spec
**Date:** 2026-03-26
**Feature:** Mix & Match Ideas Tab in Content Studio
**Status:** Approved

---

## Overview

A new "Ideas Lab" tab inside Content Studio that lets the user browse posts from all sources (LinkedIn feed, Reddit, RSS, own generated posts), pin 2–5 posts, tag specific excerpts by type (Hook, Stat, Story, Insight, Example), auto-generate an editable synthesis brief from the selections, and generate a final LinkedIn post from that brief — either inline or by sending to the existing Generator tab.

---

## Tab Structure

ContentStudio gets a two-tab bar at the top of the page:

- **Generate** — all existing content (research panel, Quick/Structured modes, output, post queue)
- **Ideas Lab** — new mix & match interface

No other pages are affected. Tab state is held in ContentStudio parent component.

---

## Data Layer

### Sources (no new DB tables)

| Label | DB Table | Fields used |
|---|---|---|
| LinkedIn | `posts` | `id`, `text`, `author_name`, `url`, `created_at` |
| Reddit / RSS / HN | `research_snippets` | `id`, `title`, `snippet`, `source`, `engagement_signal`, `url`, `fetched_at` |
| My Posts | `scheduled_posts` | `id`, `post_text`, `topic`, `status`, `scheduled_at` |

### New Backend Endpoints

#### `GET /content/idea-pool`
Returns a unified, normalized list of content items for the Ideas Lab pool.

**Query params:**
- `q` — keyword search string (optional)
- `source` — one of `all | linkedin | reddit | rss | my_posts` (default: `all`)
- `topic` — if provided, results are relevance-ranked by keyword overlap with this string
- `limit` — default 30
- `offset` — default 0

**Response item shape:**
```json
{
  "id": "string",
  "source_type": "LINKEDIN | REDDIT | RSS | HN | MY_POST",
  "title": "string | null",
  "text": "string",
  "url": "string | null",
  "date": "ISO string",
  "engagement_score": 0.0
}
```

**Ranking:** If `topic` is provided, items are scored by keyword overlap (case-insensitive token match between topic string and item title+text). No embeddings — keyword match is sufficient. Items with no overlap still appear, ranked last.

---

#### `POST /content/synthesize-brief`
Calls Groq to assemble a natural-language synthesis brief from pinned posts and tagged highlights.

**Request:**
```json
{
  "selections": [
    {
      "id": "string",
      "source_type": "string",
      "full_text": "string",
      "highlights": [
        { "text": "string", "tag": "Hook | Stat | Story | Insight | Example" }
      ]
    }
  ]
}
```

**Behaviour:**
- If highlights exist, the brief is built primarily from them (tagged excerpts listed by type)
- If no highlights exist for a selection, first 300 chars of `full_text` are used as fallback
- Groq prompt instructs the model to return a concise, directive synthesis brief (3–6 sentences) describing how to combine the materials into a LinkedIn post

**Response:**
```json
{ "brief": "string" }
```

---

#### `POST /content/generate-from-brief`
Generates a LinkedIn post from a synthesis brief, using the existing `structured_post` prompt with the brief injected as context.

**Request:**
```json
{
  "brief": "string",
  "topic": "string",
  "style": "string",
  "tone": "string",
  "word_count": 150
}
```

**Response:**
```json
{ "post": "string" }
```

Uses `build_ai_client("generation")` — Groq only, same as existing generate endpoints.

---

## Frontend Components

### New files
- `ui/src/pages/IdeasLab.jsx` — top-level Ideas Lab tab content; owns shared state
- `ui/src/components/IdeaPoolPanel.jsx` — left panel (browse, search, filter, pin)
- `ui/src/components/MixBoard.jsx` — right panel (pinned cards, highlight tagging, brief, generate)

### Modified files
- `ui/src/pages/ContentStudio.jsx` — adds two-tab bar at top; renders `<IdeasLab />` or existing content based on active tab; passes `onSendToGenerator(brief)` callback to IdeasLab

### New API client methods (in `ui/src/api/client.js`, `content` export)
- `ideaPool({ q, source, topic, limit, offset })`
- `synthesizeBrief(selections)`
- `generateFromBrief({ brief, topic, style, tone, word_count })`

---

## UI Layout

### Left Panel — Idea Pool (~45% width)

From top to bottom:

1. **Search bar** — fires `GET /content/idea-pool?q=...` on input, 300ms debounce
2. **Topic surfacing row** — text input + "Surface Ideas" button; re-queries with `topic=...` param, results re-ranked by relevance
3. **Source filter chips** — `All` · `LinkedIn` · `Reddit` · `RSS` · `My Posts` — single-select
4. **Post card list** (scrollable):
   - Source badge (colour-coded: orange=Reddit, blue=RSS, sky=LinkedIn, amber=HN, violet=My Posts)
   - Title or first 80 chars of text
   - Engagement score (muted)
   - Date
   - **Pin button** — disabled + tooltip "Unpin a post to add another" when 5 posts already pinned; turns to "Pinned ✓" after pinning

### Right Panel — Mix Board (~55% width)

Three stacked zones:

**Zone 1 — Pinned Posts** (~40% panel height, scrollable)
- Each pinned card shows full text
- Hover hint: "Select text to tag"
- Text selection → floating popover with tag buttons: `Hook` · `Stat` · `Story` · `Insight` · `Example`
- Tagged text shown with coloured underline per tag type
- Click tagged text to remove tag
- X button top-right to unpin

**Zone 2 — Synthesis Brief** (~30% panel height)
- "Build Brief" button — disabled until ≥1 post pinned; shows spinner during API call
- Editable textarea, auto-populated from `POST /content/synthesize-brief` response
- Character counter
- User can freely edit at any time

**Zone 3 — Generate Controls** (~30% panel height)
- Compact inline row: Style selector · Tone selector · Word Count input
- Two buttons:
  - **Generate here** — disabled until brief has content; spinner during call; result appears below controls inline; re-generate replaces previous result; Copy button on result; "Send to Generator" link also appears alongside result
  - **Send to Generator** — disabled until brief has content; switches to Generate tab, injects brief into `core_insight` field, forces `generationMode = 'structured'`; banner in Generate tab: *"Brief loaded from Ideas Lab"* with X to dismiss

---

## Interaction Flow

1. User opens Ideas Lab tab
2. Pool loads with default `source=all`, no search
3. User optionally types a topic → clicks "Surface Ideas" → results re-rank
4. User optionally filters by source chip
5. User pins 1–5 posts
6. User optionally selects text in pinned cards and tags excerpts
7. User clicks "Build Brief" → brief textarea populates
8. User edits brief if needed
9. User clicks "Generate here" → inline post appears
   - OR clicks "Send to Generator" → switches tab, brief pre-fills Structured form

---

## State

All state lives in `IdeasLab.jsx` (not ContentStudio parent, except the `onSendToGenerator` callback):

```
poolItems[]         — current search results
poolLoading         — bool
pinnedItems[]       — [{id, sourceType, title, text, highlights[]}]
synthesisbrief      — string
briefLoading        — bool
inlineResult        — string | null
generateLoading     — bool
activeSource        — 'all' | 'linkedin' | 'reddit' | 'rss' | 'my_posts'
searchQuery         — string
topicQuery          — string
```

State persists across tab switches within the session (React state in IdeasLab component, which mounts once). Refreshing the page clears the board — no DB persistence.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Search returns no results | Muted message: "No posts found — try a different keyword or source" |
| LinkedIn source selected, no posts in DB | Hint: "No posts scanned yet — start the engine to scan LinkedIn" |
| Build Brief with no highlights | Brief built from first 300 chars of each pinned post's full text — no error |
| Build Brief with nothing pinned | Button disabled |
| Generate with empty brief | Both generate buttons disabled |
| API error on synthesize or generate | Inline error message below button; Retry button shown |
| 5 posts already pinned | Pin buttons disabled on pool cards; tooltip shown |

---

## Out of Scope

- Persisting mix board to DB across sessions
- Sharing or exporting a brief
- Multi-user collaboration
- Drag-to-reorder pinned posts
- Semantic / embedding-based search
- Touch / mobile text selection tagging
