# Backend Deployment Notes

This backend can run as a stateless FastAPI container for the radar-only v0.
The container intentionally does not require external Postgres by default.

## Local Docker From Windows 11 + WSL

Use Docker Desktop on Windows with WSL integration enabled for Ubuntu.
Do not install Docker Engine separately inside WSL.

1. Open Docker Desktop.
2. Go to Settings -> Resources -> WSL integration.
3. Enable integration for Ubuntu.
4. Restart the WSL terminal.
5. Verify Docker is visible inside WSL:

```bash
docker --version
docker compose version
```

Build the backend image from the repository root:

```bash
docker build -t job-search-api:local .
```

Run the API container:

```bash
docker run --rm \
  --name job-search-api \
  -p 8000:8000 \
  -e TAVILY_API_KEY="$TAVILY_API_KEY" \
  -e CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]' \
  job-search-api:local
```

Check the API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/radar/profiles
```

The Docker image sets:

- `DATABASE_URL=sqlite:////tmp/job_radar.db`
- `INITIALIZE_DATABASE=false`

That keeps the radar API usable without external Postgres. The database-backed
candidate/job analysis endpoints are still part of the codebase, but they are
not the deployment focus for this v0.

## AWS Direction

Recommended backend path:

1. Build the Docker image.
2. Push it to Amazon ECR.
3. Run it with Amazon ECS Express Mode.
4. Store `TAVILY_API_KEY` as an environment variable or secret.
5. Configure CORS to allow the deployed frontend origin.
6. See `deploy/README.md` for the GitHub Actions deployment workflow, IAM policies, monitoring, and rollback instructions.
