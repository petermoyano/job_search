# Optional external job-search providers

The normal Radar `source=configured` registry includes Serper, SerpApi Google
Jobs and JSearch. For saved profiles, enabled providers are appended to the
existing source order unless their ID is already present. An explicitly
disabled entry stays disabled. The existing result target and time budget
still stop the run; earlier sources retain priority.

All results use existing RawDiscovery objects, hydration, normalization,
exact deduplication, classification, persistence and display. Only discovery
source enum values were added; no database migration or new UI is needed.
Crane document/knowledge routes, authentication and models are unchanged.

| Connector / source ID | Request and fields |
| --- | --- |
| Serper / `serper` | POST Google Search, X-API-KEY header, LinkedIn job-page site query; title, URL, snippet, origin domain. No inferred company/location/date. |
| SerpApiGoogleJobs / `serpapi_google_jobs` | GET search.json with engine=google_jobs; job ID, title, company, location, description, apply links, publisher, employment type, remote indicator and posting age. |
| JSearch / `jsearch` | GET https://jsearch.p.rapidapi.com/search-v2 with RapidAPI key/host headers; current data.jobs schema, job/employer/location/description, apply links, publisher, employment type, remote indicator and posting timestamp. |

Queries come from existing profile queries, including their location context.
If absent, target roles plus the profile location policy are used. Prose
location policies are not passed as a provider city/country parameter.
Each connector makes at most two requests per discovery call, one first page
per query; JSearch requests num_pages=1. There is no cursor crawling or extra
title/relevance filtering. The CLI accepts each source ID above.

Missing keys skip HTTP calls. Request failures log a safe provider error code
and let other sources continue. Error bodies and authenticated URLs are never
included in these connector error logs.

## Configuration and migration

Local development supports optional TAVILY_API_KEY, SERPER_API_KEY,
SERPAPI_API_KEY and RAPIDAPI_KEY environment/dotenv variables without AWS.

Production sets the nonsecret JOB_SEARCH_EXTERNAL_API_SECRET_NAME to
job-search/external-api-keys. Settings load its JSON once per process/name/region
and fill missing credentials. In production, aggregate values take precedence
over legacy environment values; locally, explicit environment/dotenv values
take precedence. Missing/unavailable/malformed secrets preserve environment
configuration with a concise warning. Missing individual keys disable their
connectors. Restart/redeploy API containers after key changes to refresh the
startup cache.

Run the safe migration from the repository root:

```bash
.venv/bin/python deploy/migrate_external_api_keys.py --profile job-search --region sa-east-1
```

It uses AWS CLI, reads only the old Tavily and aggregate secret values, merges
absent properties, preserves existing/unknown properties, rejects a detected
concurrent version change, and verifies the write. It inspects local provider
credentials, omits missing keys, uses private temporary CLI input, and prints
only key names. It never reads document-client SecretStrings or deletes secrets.

The runtime policy allows only GetSecretValue on the aggregate. CloudFormation
scopes access to the configured name plus AWS's six-character ARN suffix.
Existing document/Crane policies remain unchanged.

Retain the old Tavily secret until deployment and aggregate use are verified.
The retired deploy/ecs-task-definition.json still records its historical
reference and must not be used as a current deployment configuration.

## Documentation checked before implementation

Context7:
- /websites/serper_dev: organic result schema.
- /websites/serpapi: Google Jobs engine, parameters, fields and token pagination.
- /websites/openwebninja_api_jsearch: V2 endpoint and data.jobs schema.
- /python/cpython: urllib.request headers, timeouts and HTTP errors.
- /boto/boto3: Secrets Manager get_secret_value, region and retry configuration.
- /pydantic/pydantic-settings: environment/dotenv precedence.

Official references also inspected:
[Serper](https://serper.dev/),
[SerpApi](https://serpapi.com/google-jobs-api),
[JSearch RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch/playground),
[JSearch schema](https://www.openwebninja.com/api/jsearch/docs), and
[RapidAPI authentication](https://docs.rapidapi.com/docs/configuring-api-security).
The RapidAPI page exposed /search-v2 and jsearch.p.rapidapi.com. The direct
OpenWeb Ninja endpoint uses different authentication and is not used here.

## Migration status (2026-09-08)

Tavily's real credential was copied into the aggregate; the other three keys
were unavailable and remain absent. Two bounded manual Tavily attempts from
the new image reached HTTP 432 (Plan Limit Exceeded). The aggregate loaded
successfully, but successful job retrieval is still unverified.

Keep the old Tavily secret, its CloudFormation parameter and legacy Lambda
environment value until a live aggregate-backed search succeeds. The new
loader uses the aggregate in production and keeps the old environment as a
fallback if Secrets Manager is unavailable. After validation, remove that
legacy parameter/environment reference, check operational references and
schedule normal secret deletion with a recovery window. Never force-delete.


## Deployment and validation (2026-09-08)

CloudFormation stack job-search-lambda in sa-east-1 reached UPDATE_COMPLETE.
The API uses the existing ECR repository with image tag
external-connectors-20260908T125641Z
(digest sha256:403560b83f83bee5e943d1d6d80797806d1ac02190f2fd843fa43c4b4893a476).
Only the API function and its execution-role policy changed; the Function URL
had a dependency reevaluation and kept the same URL. Worker images and all
other resource definitions were preserved.

Live health and frontend CORS checks passed (HTTP 200). The deployed OpenAPI
schema contains all three provider source values. The actual container starts
without any provider keys. Aggregate loading succeeded in the image; Tavily
search validation remains blocked by its HTTP 432 plan-limit response.
No new-provider quota was used.

All 192 tests passed. Ruff lint and changed-file formatting passed.
The six new/affected connector, configuration and orchestration modules pass
targeted mypy checks. Full-app mypy reports 84 existing errors in 20 files,
with exactly the same error set as untouched HEAD.

AWS now has the aggregate secret containing TAVILY_API_KEY only.
ReadExternalApiKeys grants only secretsmanager:GetSecretValue on that secret
name plus its six-character AWS suffix. Existing IAM policies were compared
before and after and were unchanged. Both document-client secrets remain
separate. Crane/document secret version metadata, change/rotation state and
tags were compared and unchanged; their SecretStrings were never retrieved.
The old Tavily secret is intact and no deletion was scheduled.

Remaining actions: resolve Tavily's plan limit, provide SERPER_API_KEY,
SERPAPI_API_KEY and RAPIDAPI_KEY when available, then refresh API containers.
After a successful Tavily search through the aggregate, complete the staged
legacy fallback/reference cleanup and consider recovery-window deletion.
No Git commit or push was made.

## Files changed

- app/core/config.py
- app/api/routes.py
- app/radar/__main__.py
- app/radar/discovery.py
- app/radar/models.py
- app/radar/connectors/external.py
- app/radar/connectors/serper.py
- app/radar/connectors/serpapi_google_jobs.py
- app/radar/connectors/jsearch.py
- deploy/lambda-template.yaml
- deploy/migrate_external_api_keys.py
- deploy/README.md
- .env.example
- tests/conftest.py
- tests/test_external_api_settings.py
- tests/test_external_connectors.py
- docs/external-job-search.md

CloudTrail additionally confirmed a successful aggregate GetSecretValue by
the job-search-lambda-execution runtime role at 2026-09-08T13:01:39Z.
