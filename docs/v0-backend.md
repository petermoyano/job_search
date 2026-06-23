# v0 Backend

This repository now contains a backend-only FastAPI MVP for Direct Product Job Radar.

Implemented pieces:

* SQLAlchemy models for users, candidate profiles, CVs, companies, sources, job leads, analyses, score breakdowns, detected signals, human decisions, and app config
* Alembic initial migration
* LangGraph job analysis workflow
* Deterministic CV/profile and job fact extraction, with an optional LLM structured-output hook for CV parsing
* Transparent scoring for directness, product ownership, technical fit, AI depth, and process safety
* Deal-breaker detection
* Human decision tracking
* Sample candidate and job inputs
* Basic scoring, workflow, and API tests

## Local Setup

Copy the environment template and start Postgres:

```bash
cp .env.example .env
docker compose up -d
```

Run migrations:

```bash
uv run alembic upgrade head
```

Start the API:

```bash
uv run fastapi dev app/main.py
```

The app also creates missing tables on startup for local convenience, but Alembic is the canonical schema path.

Run tests:

```bash
uv run pytest
```

## API Endpoints

Useful endpoints:

* `GET /health`
* `POST /profiles`
* `GET /profiles`
* `POST /cvs/extract`
* `POST /cvs`
* `POST /jobs`
* `POST /jobs/analyze`
* `POST /jobs/{job_id}/analyze`
* `GET /jobs`
* `GET /jobs/{job_id}/analysis`
* `GET /analyses`
* `POST /jobs/{job_id}/decisions`
* `GET /config/scoring`

## Example

Create a candidate profile:

```bash
curl -X POST http://localhost:8000/profiles \
  -H "Content-Type: application/json" \
  --data @samples/candidate_profile.json
```

Analyze a job:

```bash
curl -X POST http://localhost:8000/jobs/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "title": "AI Product Engineer",
    "company_name": "Acme AI",
    "raw_text": "Company: Acme AI\nRole: AI Product Engineer\nWe are hiring directly for our product engineering team building our own SaaS platform with Python, LangGraph, RAG, agents, and embeddings. Salary range: USD 150,000 - 180,000."
  }'
```
