# BlogPilot — User Guide

## Getting Started

### Option A: Run the EXE (Recommended)
1. Double-click **BlogPilot.exe** — your browser opens automatically
2. Go to **Settings** and enter your **Groq API key** (get one free at [console.groq.com](https://console.groq.com))
3. Go to **Settings > LinkedIn** and enter your LinkedIn email and password (stored encrypted on your machine)
4. Go to **Topics** and configure what topics you want to engage with
5. Go to **Dashboard** and click **Start Engine**

### Option B: Run from Source
```bash
# Terminal 1 — Backend
pip install -r requirements.txt
python launcher.py

# Browser opens automatically to http://127.0.0.1:8000
```

---

## Pages Overview

### Dashboard
Your home base. Shows:
- **Engine status** — Start, Stop, or Pause the engine
- **Daily budget bars** — how many likes/comments/connections used today
- **Activity feed** — live log of everything the engine does

### Topics
Configure what the AI looks for in your LinkedIn feed:
- **Add/remove topics** — the AI scores posts against these
- **Hashtags** — posts with these hashtags are scanned first
- **Blacklist keywords** — posts with these words are always skipped
- **Minimum score** — only engage with posts scoring above this (default: 6/10)

### Feed Engagement
Control how the engine interacts with posts:
- **Mode**: Like only, Comment only, Like + Comment, or Smart (auto-decides based on score)
- **Preview comments** — toggle to review AI comments before they're posted
- View recent posts, skipped posts, and comment history

### Content Studio
Create and schedule your own LinkedIn posts:
1. Pick a topic, style (Thought Leadership, Story, Tips List, etc.), and tone
2. Click **Generate** — the AI writes a draft
3. Edit as needed
4. Click **Post Now** or **Schedule** for later

### Campaigns
Set up multi-step outreach sequences:
1. Click **New Campaign**
2. Add steps: Visit Profile → Follow → Connect (with note) → Message
3. Set delays between steps (e.g., wait 3 days)
4. Enroll leads by pasting LinkedIn profile URLs

### Leads
Everyone the engine discovers:
- See name, title, company, email, and status
- **Enrich** — find their email address automatically
- **Export CSV** — download your lead list
- **Enroll** — add leads to a campaign

### Analytics
Track your performance:
- Daily/weekly action charts
- Top performing topics
- Campaign conversion funnel
- Content quality metrics

### Prompt Editor
Customize the AI's writing style:
- Edit the prompts the AI uses for comments, posts, connection notes, and replies
- **Test** any prompt with sample data before saving
- **Reset to Default** if you want to start over

### Settings
- **AI Config** — Groq API key, model selection, temperature
- **LinkedIn** — credentials (encrypted, never shown)
- **Rate Limits** — daily caps per action type
- **Delays** — timing between actions (for safety)
- **Danger Zone** — restart server, shut down, clear data

---

## Daily Budget Defaults

| Action | Daily Limit |
|--------|-------------|
| Likes | 30 |
| Comments | 12 |
| Connections | 15 |
| Profile Visits | 50 |
| Posts | 5 |
| InMails | 5 |

These reset at midnight. Change them in **Settings > Rate Limits**.

---

## Safety Tips

- **Start with low budgets** (e.g., 10 likes, 5 comments) and increase gradually
- **Enable comment preview** until you trust the AI's output
- **Don't run 24/7** — set active hours in Engine Control (e.g., 9 AM - 6 PM)
- **Check Analytics weekly** — if engagement drops, adjust your topics
- The engine auto-pauses if it detects unusual activity (CAPTCHA, errors)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Browser won't open | Go to http://127.0.0.1:8000 manually |
| "GROQ_API_KEY not configured" | Enter your key in Settings > AI Config |
| Engine stuck in ERROR state | Click Stop, then Start again |
| Comments sound robotic | Edit prompts in Prompt Editor, test before saving |
| LinkedIn security challenge | Complete the challenge manually, engine auto-resumes |

---

## Building the EXE

If you want to rebuild after making changes:

```bash
build.bat
```

Or manually:
```bash
cd ui && npm run build && cd ..
pyinstaller blogpilot.spec --noconfirm
```

Output: `dist/BlogPilot/BlogPilot.exe`
