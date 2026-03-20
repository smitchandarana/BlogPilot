# BlogPilot — Quick Start

## Option A: EXE (Recommended — no Python required)

### 1. Install
Run **BlogPilot-Setup-1.0.0.exe** → follow the wizard → tick "Create Desktop shortcut".

Or, if you have the raw build folder, run `scripts\create_shortcut.bat` to add a Desktop shortcut.

### 2. First Launch
Double-click the **BlogPilot** shortcut.
Your browser opens automatically to `http://127.0.0.1:8000`.

A **setup wizard** walks you through 3 steps:

| Step | What to do |
|------|-----------|
| 1. Groq API Key | Paste your key from [console.groq.com/keys](https://console.groq.com/keys) → **Test** → **Save & Continue** |
| 2. LinkedIn Account | Enter LinkedIn email + password → **Test Login** → **Save & Continue** (or Skip for now) |
| 3. Topics | Pick the topics relevant to your audience → **Continue** |

Click **Launch Dashboard** — you're done.

### 3. Start the Engine
On the Dashboard, click the big **Start Engine** button.
The engine begins scanning your LinkedIn feed immediately.

---

## Option B: Run from Source (developers)

```bash
# Backend (Terminal 1)
pip install -r requirements.txt
python launcher.py          # opens browser automatically at http://127.0.0.1:8000

# Frontend dev server (Terminal 2) — only needed when editing UI code
cd ui && npm run dev        # http://localhost:3000
```

---

## Second Launch

On subsequent launches (EXE or source), the setup wizard is **automatically skipped**
if your API keys are already saved. The Dashboard loads directly.

---

## Shutdown

**From the UI:** Settings → Danger Zone → **Shut Down**

**From the terminal:** `Ctrl+C`

---

## Key Facts

- Backend: **port 8000** | Frontend (EXE): also **8000** | Frontend (dev): port 3000
- Engine starts **STOPPED** — click Start Engine each session
- Daily budgets reset at midnight automatically
- Default limits: 30 likes · 12 comments · 15 connections per day
- If LinkedIn shows a CAPTCHA: complete it manually — engine resumes automatically
- Engine auto-pauses on repeated errors (circuit breaker) — click Stop → Start to reset
