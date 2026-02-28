# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**回忆录 (Biography)** — An AI-powered app that helps elderly people (60+) record life stories through real-time voice conversations, then generates written memoirs. The system uses ByteDance Doubao for real-time voice dialogue (ASR + TTS + LLM) and Aliyun DashScope (Qwen) for text-based LLM tasks (memoir generation, summarization, topic generation).

## Development Commands

### Local Development (SQLite)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend: open `web/index.html` directly or `cd web && python -m http.server 3000`

### Docker Deployment (PostgreSQL)
```bash
cp .env.example .env  # fill in real values
docker compose up -d --build
docker compose logs -f backend  # check logs
curl http://localhost/health     # health check
```

### Database Migrations (Alembic)
```bash
cd backend
alembic revision --autogenerate -m "description"  # create migration
alembic upgrade head                               # apply migrations
```
Migrations run automatically on Docker startup via `entrypoint.sh`.

### No test suite or linter is currently configured.

## Architecture

### Three-Layer Backend (FastAPI)
- **`backend/app/api/`** — Route handlers (REST + WebSocket). Auth via `Depends(get_current_user)`.
- **`backend/app/services/`** — Business logic. LLM calls, conversation management, memoir generation, topic pool management.
- **`backend/app/models/`** — SQLAlchemy ORM models (User, Conversation, Message, Memoir, TopicCandidate).
- **`backend/app/prompts/`** — LLM prompt templates. Each module exports a `PROMPT` string and `build(**kwargs)` function.

### Real-Time Voice Dialogue Flow
```
Browser (Web Audio API, 16kHz PCM)
  ↕ WebSocket (/api/realtime/dialog)
FastAPI WebSocket handler
  ↕ WebSocket
ByteDance Doubao API (ASR → LLM → TTS, 24kHz audio)
```
Two modes: `profile_collection` (first-time user info gathering) and `normal` (topic-based conversation).

### Key Data Flow
1. **Profile Collection** → Extract user info (name, birth year, hometown) → Generate era memories (historical context for user's generation)
2. **Topic Pool** → LLM generates 8-12 conversation starters based on user profile + existing memoirs → Pool reviewed/refreshed after each conversation
3. **Conversation** → User picks topic → Real-time voice dialogue → Messages saved → Summary generated
4. **Memoir** → Conversation text → LLM generates narrative prose → Time period inferred → Ordered on timeline

### Frontend
Vanilla HTML/CSS/JS (no framework). Key files:
- `web/js/realtime-chat.js` — WebSocket audio client
- `web/js/api.js` — API client (fetch wrapper with JWT auth from localStorage)

### Config
`backend/app/config.py` uses pydantic-settings `BaseSettings`, reads from `.env`. SQLite by default; set `DATABASE_URL` for PostgreSQL.

## Key Conventions

- All API routes are prefixed with `/api/`. Router registration is in `backend/app/api/__init__.py`.
- JWT auth (HS256). Admin endpoints use `X-Admin-Key` header.
- LLM prompts use `{placeholder}` formatting. Add new prompts as separate modules in `backend/app/prompts/`.
- CORS is restricted to production domains + `localhost:8080`. Update `backend/app/main.py` if adding origins.
- PostgreSQL managed by Alembic migrations; SQLite uses auto-create (`Base.metadata.create_all`).
- Background tasks (memoir generation, topic pool review, era memories) run via FastAPI's `BackgroundTasks`.

## Important Files

- `docs/PRD.md` — Product requirements (Chinese)
- `docs/技术方案.md` — Technical architecture spec (Chinese)
- `DEPLOY.md` — Docker deployment guide
- `backend/app/services/doubao_realtime.py` — ByteDance Doubao WebSocket client
- `backend/app/services/llm_service.py` — All DashScope/Qwen LLM interactions
- `backend/app/services/topic_service.py` — Topic pool generation and review logic
