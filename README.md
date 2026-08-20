# Webo

Webo is an AI research assistant that combines web search, streaming responses, chat memory, and traceable job execution in one system.

It is built as a full-stack app, not just a prompt wrapper. Queries are created as jobs, streamed live to the client, persisted for reconnects, and can be cancelled from the backend.

## Features

- Stream answers in real time with Server-Sent Events
- Route queries between chat-only, memory-only, and live web research paths
- Support both workflow mode and agentic research mode
- Collect sources and synthesize evidence-backed responses
- Persist chat and job state with Redis and Postgres
- Cancel running jobs from the backend
- Store per-job traces for debugging and inspection
- Apply guardrails for sanitization, moderation, prompt injection, and PII

## Tech Stack

- Frontend: Next.js, React, TypeScript
- Backend: FastAPI, SQLAlchemy
- Data: Postgres, Redis
- LLM / Search: Gemini, Exa, OpenAI moderation

## Project Structure

```text
webo/
├── apps/
│   ├── api/
│   └── web/
├── packages/
│   ├── database/
│   └── shared/
└── docker-compose.yml
```

## Local Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- Redis
- Postgres

### Environment Variables

```bash
GEMINI_API_KEY=...
EXA_API_KEY=...
OPENAI_API_KEY=...
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
```

### Run the Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
npm install
npm run dev:api
```

### Run the Frontend

```bash
cd apps/web
npm install
npm run dev
```

Frontend: `http://localhost:3000`  
Backend: `http://localhost:8000`

## Docker

```bash
docker compose up --build
```

This starts:

- Next.js frontend
- FastAPI backend
- Redis
- Postgres
