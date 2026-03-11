# LinkedIn AI Growth Engine

Local-first LinkedIn automation with AI-powered engagement, lead capture, and email enrichment.

---

## Quick Start

### 1. Clone and set up backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
# Copy and edit settings
cp config/settings.yaml.example config/settings.yaml

# Add your API keys (stored encrypted)
python utils/setup_secrets.py
# Follow prompts for: Groq API key, LinkedIn credentials, Hunter.io (optional)
```

### 3. Initialise database

```bash
python -m storage.database
```

### 4. Start backend

```bash
uvicorn main:app --reload --port 8000
```

### 5. Start UI

```bash
cd ui
npm install
npm run dev
# Opens on localhost:3000
```

---

## Configuration

All settings live in `config/settings.yaml`.
The engine hot-reloads this file — no restart needed when you change settings.

**Never put API keys in settings.yaml.** Use the Settings page in the UI or run:
```bash
python utils/setup_secrets.py
```

---

## Project Structure

```
linkedin-ai-engine/
├── CLAUDE.md          ← Instructions for Claude Code
├── ARCHITECTURE.md    ← System design (read this)
├── TASKS.md           ← Build checklist (current status)
├── PROMPTS.md         ← AI prompt documentation
├── TOPICS.md          ← Default targeting config
├── requirements.txt
├── config/
│   └── settings.yaml  ← All configuration
├── prompts/           ← Editable AI prompt templates
│   ├── relevance.txt
│   ├── comment.txt
│   ├── post.txt
│   ├── note.txt
│   └── reply.txt
├── backend/           ← Python FastAPI app
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── automation/
│   ├── ai/
│   ├── growth/
│   ├── enrichment/
│   ├── storage/
│   └── utils/
└── ui/                ← React + Vite frontend
    └── src/
        ├── pages/
        ├── components/
        ├── hooks/
        └── api/
```

---

## Safety

This tool runs on your real LinkedIn account. Respect the daily limits in settings.yaml. The default limits are conservative and safe. Do not raise them significantly.

The circuit breaker auto-pauses the engine if errors spike. Do not disable it.

---

## Phase 2

Once all Phase 1 milestones are complete (see TASKS.md), the system converts to a Chrome Extension. See ARCHITECTURE.md for the conversion map.
