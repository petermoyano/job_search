# Backend Deployment Notes

This backend can run as a stateless FastAPI container for the radar-only v0.
The container intentionally does not require external Postgres by default.

## Local Docker From Windows 11 + WSL

Use Docker Desktop with WSL integration enabled for Ubuntu. Build the ordinary
local image from the repository root:

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

The container sets:

- `DATABASE_URL=sqlite:////tmp/job_radar.db`
- `INITIALIZE_DATABASE=false`

That keeps the radar API usable without external Postgres. The database-backed
candidate/job analysis endpoints remain in the codebase, but they are not the
deployment focus for this v0.

## AWS Lambda Direction

Production uses an on-demand Lambda container and Function URL:

1. Build `Dockerfile.lambda`, which adds AWS Lambda Web Adapter to the existing
   FastAPI/uvicorn application without changing application routing.
2. Push an immutable image to the existing ECR repository.
3. Deploy `deploy/lambda-template.yaml` outside a VPC.
4. Resolve `TAVILY_API_KEY` from Secrets Manager into the function environment.
5. Restrict CORS to the deployed Vercel frontend origin.
6. Rely on the account's current regional concurrency quota of 10 and retain
   Lambda logs for 14 days.
7. Use `.github/workflows/deploy.yml` for subsequent image deployments.

The Function URL is public so the browser can call it directly. CORS limits
browser origins but is not authentication; add an authenticated API or trusted
server-side proxy before exposing paid operations to additional users.
