# BlogPilot — User Guide

## What It Does

BlogPilot automates LinkedIn engagement on your behalf:
- Scans your feed and scores posts with AI (Groq)
- Likes and comments on relevant posts (with your review before posting)
- Visits profiles of high-value leads and captures their details
- Finds business email addresses via pattern matching + SMTP verification
- Generates and schedules your own LinkedIn posts
- Tracks everything in an analytics dashboard

> **Risk notice:** This tool automates LinkedIn interactions which may violate LinkedIn's Terms of Service (Section 8.2). Use at your own risk. See NOTICE.txt for the full disclosure.

---

## Installation

### EXE Install (Windows, no Python required)

1. Run **BlogPilot-Setup-1.0.0.exe**
2. Follow the installer wizard
3. Tick **"Create Desktop shortcut"** on the Additional Tasks screen
4. Click **Finish** → app launches automatically

To reinstall after an update: run the new Setup EXE — your saved API keys, LinkedIn session, and database are preserved.

### Run from Source

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers (first time only)
playwright install chromium

# 3. Start the backend (opens browser automatically)
python launcher.py
```

---

## First-Run Setup Wizard

On first launch, a 3-step wizard configures everything:

### Step 1 — Groq API Key
- Go to [console.groq.com/keys](https://console.groq.com/keys) and create a free API key
- Paste it into the wizard and click **Test** to verify
- Click **Save & Continue**

### Step 2 — LinkedIn Account
- Enter your LinkedIn email and password
- Credentials are encrypted on disk (Fernet AES encryption) — never stored in plaintext
- Click **Test Login** to verify, then **Save & Continue**
- You can click **Skip for now** and add credentials later in Settings

### Step 3 — Target Topics
- Select which topics your LinkedIn audience cares about
- The AI uses these to score every post (0–10) and decide whether to engage
- Add custom topics if needed, then click **Continue**

Click **Launch Dashboard** — setup is complete. The wizard is skipped on all future launches.

---

## Dashboard

Your mission control. Always open this page first.

| Element | What it shows |
|---------|--------------|
| **Engine Toggle** | Start / Stop / Pause the engine |
| **Stat counters** | Posts scanned, liked, commented, profiles visited, emails found, leads |
| **Budget bars** | How much of today's daily limit has been used per action |
| **Activity feed** | Live scrolling log of every engine action |
| **Preview queue** | AI-generated comments awaiting your approval |
| **Intelligence widget** | Content insights extracted from research |

### Comment Preview Queue
When **Preview Comments** is enabled (default), comments are held for your review:
- **Edit** — rewrite the AI's comment before posting
- **Approve** — posts the comment to LinkedIn
- **Reject** — skips the post, no action taken

---

## Settings

Settings → AI Configuration:

| Setting | Description |
|---------|-------------|
| **Groq API Key** | Required. Used for comment generation, post writing, scoring. |
| **OpenRouter API Key** | Recommended. Used for background tasks: topic research, content extraction, relevance scoring. Free at [openrouter.ai](https://openrouter.ai/keys). If not set, Groq handles everything (burns your daily Groq quota faster). |
| **Model** | Groq model for generation (default: llama-3.3-70b-versatile) |
| **Temperature** | Creativity level 0–1 (default: 0.7) |

Settings → LinkedIn:
- Update your LinkedIn email/password here after the wizard
- Credentials are re-encrypted on save

Settings → Rate Limits:
- Set daily caps per action type
- Start conservative — increase only after the engine has run cleanly for a week

Settings → Delays:
- Minimum/maximum wait time before each action
- Longer delays = lower detection risk

Settings → Danger Zone:
- **Restart Server** — restarts the backend (reconnects browser session)
- **Shut Down** — cleanly stops everything
- **Clear All Data** — wipes the database (leads, posts, analytics) — irreversible

---

## Engine Control

Configure the automation schedule:

- **Active Hours** — e.g., 9 AM to 6 PM (engine pauses outside these hours)
- **Active Days** — which days of the week to run
- **Feed Scan Interval** — how often to scan the feed (default: 20 minutes)
- **Module Toggles** — enable/disable feed engagement, campaigns, email enrichment, etc.

---

## Topics

What the AI looks for:

- **Topics** — the AI scores posts against these (0–10). Posts scoring ≥ 6 are engaged with.
- **Hashtags** — feeds with these hashtags are scanned first (priority scanning)
- **Keyword Blacklist** — posts containing these words are always skipped
- **Industries / Job Titles** — used to prioritise high-value leads for email enrichment
- **Minimum Score** — slider to set the engagement threshold (default: 6)

Score thresholds (configurable):

| Score | Action |
|-------|--------|
| 0–5 | Skip — not relevant |
| 6–7 | Like only |
| 8–9 | Like + Comment + Profile visit |
| 10 | Like + Comment + Profile visit + Connection request |

---

## Content Studio

Write and schedule your own LinkedIn posts:

1. **Quick Mode** — pick topic, style, tone → Generate → edit → Post Now or Schedule
2. **Structured Mode** — fill in audience, pain point, hook intent, proof type → generates a grounded post using real insights from your research
3. **Intelligence Panel** — click any research pattern to fill the structured form automatically
4. **Write Like My Best Posts** — uses your top-performing past posts as style reference

Styles: Thought Leadership · Story · Tips List · Question · Data Insight · Contrarian Take

---

## Leads

Everyone the engine discovers while visiting profiles:

- **Email Status**: Not Found · Found · Verified · Bounced
- **Enrich** — triggers email search (pattern matching + SMTP verification)
- **Enrich All** — bulk enrichment for all leads without emails
- **Export CSV** — downloads your full lead list
- **Enroll** — adds selected leads to an outreach campaign

---

## Campaigns

Multi-step automated outreach sequences:

1. Click **New Campaign** → name it
2. Add steps: Visit Profile → Follow → Connect (with AI note) → Message → Wait (X days)
3. Save the campaign
4. **Enroll** leads by pasting LinkedIn profile URLs
5. The engine executes steps automatically at the configured delay intervals

---

## Analytics

- **Daily / Weekly charts** — actions by type over time
- **Top Topics** — which topics drive the most engagement
- **Campaign Funnel** — enrolled → connected → replied → converted
- **Learning Insights** — comment quality trends, best performing angles, optimal posting times

---

## AI Keys — Which Does What

| Task | Provider | Why |
|------|----------|-----|
| Comment generation | **Groq** | Fast, high quality, needed in real-time |
| Post generation | **Groq** | User-facing, quality matters |
| Relevance scoring | **OpenRouter** | Background batch, free tier sufficient |
| Topic research extraction | **OpenRouter** | Background batch, runs every 4 hours |
| Content insight extraction | **OpenRouter** | Background batch |

If you only have Groq: everything works but background tasks will consume your daily Groq token quota (100k/day on free tier). Adding an OpenRouter key preserves your Groq quota for generation tasks only.

---

## Daily Budget Defaults

| Action | Limit | Change in |
|--------|-------|-----------|
| Likes | 30/day | Settings → Rate Limits |
| Comments | 12/day | Settings → Rate Limits |
| Connections | 15/day | Settings → Rate Limits |
| Profile Visits | 50/day | Settings → Rate Limits |
| Posts Published | 5/day | Settings → Rate Limits |
| InMails | 5/day | Settings → Rate Limits |

Budgets reset at midnight (local time). Current usage shown as bars on the Dashboard.

---

## Safety Recommendations

- **Start with half the default limits** for the first week — gives LinkedIn time to adjust to your activity pattern
- **Enable Comment Preview** until you fully trust the AI output
- **Set active hours** — don't run 24/7 (Engine Control → Activity Window)
- **Review the Activity Feed daily** — catch any unexpected actions early
- **If the engine auto-pauses** (circuit breaker): check the Alert banner on Dashboard, wait 30 minutes, then click Stop → Start

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Browser doesn't open | Go to `http://127.0.0.1:8000` manually |
| Setup wizard shows every time | Wait 2–3 seconds on Dashboard load — it checks your saved keys and skips automatically |
| "Groq API key not configured" alert | Settings → AI Configuration → enter your Groq key |
| Engine stuck in ERROR state | Dashboard → Stop → Start Engine |
| LinkedIn CAPTCHA appeared | Complete it manually in the browser window — engine auto-resumes |
| Comments sound robotic | Prompt Editor → edit the `comment` prompt → test with sample posts → save |
| No posts appearing in feed | Check Topics — minimum score may be too high, or topics too narrow |
| Email enrichment finds nothing | Normal for 2nd/3rd degree connections — enable Hunter.io API in Settings for better coverage |

---

## Rebuilding the EXE

After making code changes:

```bash
# 1. Build the React frontend
cd ui && npm run build && cd ..

# 2. Package as EXE
pyinstaller blogpilot.spec --noconfirm

# 3. (Optional) Create installer — requires Inno Setup 6
iscc installer.iss
```

Output: `dist/BlogPilot/BlogPilot.exe`
Installer: `dist/BlogPilot-Setup-1.0.0.exe`

---

## File Locations (EXE Mode)

All writable files are stored next to `BlogPilot.exe`:

| Path | Contents |
|------|----------|
| `config/settings.yaml` | All settings (rate limits, topics, schedule) |
| `config/.secrets/groq.json` | Encrypted Groq API key |
| `config/.secrets/openrouter.json` | Encrypted OpenRouter API key |
| `config/.secrets/linkedin.json` | Encrypted LinkedIn credentials |
| `config/.secrets/.api_token` | Local bearer token (auto-generated) |
| `data/engine.db` | SQLite database (posts, leads, actions, analytics) |
| `logs/engine.log` | Rotating log (10MB × 5 files) |
| `browser_profile/` | Playwright browser profile (LinkedIn session cookies) |
