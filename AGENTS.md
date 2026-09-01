## Shell environment

This repository lives in Ubuntu WSL. For all repository inspection,
development, tests, and Git operations, use:

wsl -d Ubuntu -- bash -lc '<command>'

Use Linux paths such as `/home/peter/job_search`; do not use Windows-native
shell commands or Windows paths for repository work.
## Product context

This repository is the shared backend for both `job_search_fe` (Direct Product
Job Radar) and `151` (Crane Intelligence). Both applications currently have
zero real production users and are being developed primarily to learn AWS.

Before changing public API routes, CORS, authentication, shared database
models, deployment, or AWS infrastructure, assess the impact on both clients.
Prefer small, on-demand, pay-per-use AWS resources. Do not introduce
always-running infrastructure unless it is necessary for an explicit learning
or product objective.

Read `docs/architecture.md` before making changes that affect either client,
shared contracts, or deployment.
