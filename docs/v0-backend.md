# Retired manual job-analysis API

The manual recommendation workflow has been removed after checking both
frontend clients for callers. Discovery continues through POST /radar/runs.

Removed endpoints:

- POST /jobs and GET /jobs
- POST /jobs/analyze
- POST /jobs/{job_id}/analyze
- GET /jobs/{job_id}/analysis
- GET /analyses
- POST /jobs/{job_id}/decisions
- GET /config/scoring

The manual graph, recommendation scoring engine, and job-fact extraction
helpers were removed. Candidate profile/CV extraction, Radar discovery,
filtering, feedback, and optional reviews remain.

Existing ORM models and migrations are retained to preserve historical data
and relationships. No database or AWS changes are needed. Endpoint removal
takes effect when the backend is deployed.
