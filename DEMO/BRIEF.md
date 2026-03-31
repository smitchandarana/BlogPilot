# BlogPilot — Upwork Client Brief

**300-character pitch:**

> Python/React desktop app automating LinkedIn growth: Groq AI scores posts (0–10), generates authentic comments with 4-candidate selection, captures leads, enriches emails via SMTP. Self-learning engine tracks engagement and adapts thresholds. 761 posts processed, 22 leads in production.

---

## Screenshots

| File | Page | What it shows |
|---|---|---|
| `01-feed-engagement.png` | Feed Engagement | Real LinkedIn posts scored 6–9, ACTED/FAILED results, smart mode selector |
| `02-dashboard.png` | Dashboard | 126 posts scanned, 22 leads, Content Intelligence widget (143 insights, 76 patterns) |
| `03-content-studio.png` | Content Studio | 13 AI-researched topic cards with trending/engagement/gap scores, one-click post generation |
| `04-dashboard-live.png` | Dashboard (live) | Live activity log with real LinkedIn engagement history, daily budget bars, background task controls |
| `05-prompt-editor.png` | Prompt Editor | Full AI prompt editor with variable chips, live test panel, save/reset controls |

---

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy, SQLite, APScheduler, Playwright
- **Frontend:** React 18, Vite, Tailwind CSS, Recharts
- **AI:** Groq (llama-3.3-70b) for comments/posts, OpenRouter (Gemini Flash) for scoring/research
- **Automation:** Playwright Chromium with stealth mode + human-behavior simulation
- **Distribution:** PyInstaller single-file EXE + React dev server

## Key Features Built

- 12-step engagement pipeline (scan → score → strategy → comment → post → log)
- 4-candidate comment generation with scorer + diversity guard
- Content Intelligence: Reddit/RSS/HN research → AI-extracted subtopics → pattern aggregation
- Self-learning: tracks reply rates per angle, auto-tunes relevance thresholds
- Email enrichment: DOM scrape + pattern generation + SMTP verification
- Human-behavior simulation: random delays, typing speed, scroll patterns
- Daily budget enforcement per action type with circuit breaker
- Comment approval queue (human-in-the-loop before posting)
- 94 automated tests passing
