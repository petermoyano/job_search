# Radar Module

The radar is the job-discovery and prequalification layer of the backend. It
turns source results into a short, evidence-backed list of opportunities that
are worth showing to a candidate. Discovery is still user-triggered: the
frontend calls the run endpoint when the user presses Search. There is no
scheduler and the backend never applies to a job.

## Romina's Remote Profile

The profile ID is `romina-remote-spanish-hr`, currently versioned as
`2026-07-30.1`. It represents Romina Roby as an HR professional with more than
eight years of experience, an HRBP/Talent Acquisition focus, and a
legal/employment-relations background.

A result is eligible only when every required fact can be verified:

- The title matches a configured Tier 1, 2, or 3 HR role.
- The vacancy is explicitly fully remote.
- A candidate based in Argentina can be hired (Argentina, LATAM, global, or
  international hiring).
- The description and application action are in Spanish.
- Advanced or fluent English is not mandatory. Basic/intermediate or
  non-exclusive English is allowed.
- The role is semi-senior, senior, specialist, or an equivalent experienced
  position.
- The individual job page is still open and has an active application action.
- The role is not junior, an internship, sales, call center, general
  administration, mandatory onsite, or hybrid.

A failed check rejects the result. Missing evidence produces an ineligible
`maybe` result for audit; it is not placed in the user's main opportunity
list. This deliberately favors precision over volume.

## Ordered Source Waterfall

Romina's remote search follows this exact order:

1. InfoJobs
2. LinkedIn Jobs
3. Computrabajo Argentina
4. Bumeran
5. Indeed España
6. Get On Board
7. Hiring Room
8. Torre
9. Wellfound
10. Remote Latam
11. Workana (HR searches only)
12. Talent.com
13. Jooble

Each source is searched with Tier 1, Tier 2, and Tier 3 role queries. The next
source is queried only if the current source returns fewer than three new,
qualified results. The run also stops after five new qualified opportunities
have been collected.

For ordered profiles, the request `limit` caps both the displayed target and
the number requested from each source; it does not prevent later sources from
being searched. Each source has its own smaller `max_results` safety limit.
This is necessary for the waterfall to reach fallback sources after noisy
earlier sources.

## Verification Pipeline

For profiles with an eligibility policy, the pipeline is:

```text
ordered source search
  -> fetch individual job page and application page
  -> extract visible text and JobPosting JSON-LD
  -> normalize and deduplicate
  -> verify individual/open vacancy
  -> run deterministic eligibility gates
  -> rank eligible results
  -> suppress previously presented opportunities
  -> persist run, opportunity, evaluation, and evidence
```

Verified page and JSON-LD fields take precedence over search-engine snippets.
The persisted evaluation records facts, every eligibility check, evidence,
classifier version, score components, whether the result was new, and whether
it was presented.

## API

List profiles:

```http
GET /radar/profiles
```

Run a manual search:

```http
POST /radar/runs
Content-Type: application/json

{
  "profile_id": "romina-remote-spanish-hr",
  "source": "tavily",
  "limit": 25,
  "enable_quality_review": true
}
```

Important response fields:

- `run_id` and `profile_version` identify the persisted run and policy.
- `items` contains only new, fully eligible opportunities for Romina's
  structured profile.
- `excluded_items` contains rejects, unverified maybes, repeats, and eligible
  overflow for diagnostics.
- `total_qualified`, `total_new`, and `total_excluded` describe the run.
- `source_summaries` explains which sources ran and why the waterfall stopped.
- Every item has a stable `opportunity_id`, normalized candidate data, facts,
  eligibility checks, role tier, rank components, and evidence.

List previous runs:

```http
GET /radar/runs?profile_id=romina-remote-spanish-hr&limit=25
```

List the opportunity history (presented opportunities by default):

```http
GET /radar/opportunities?profile_id=romina-remote-spanish-hr
GET /radar/opportunities?profile_id=romina-remote-spanish-hr&include_excluded=true
```

Save or update Romina's feedback:

```http
PUT /radar/opportunities/{opportunity_id}/feedback
Content-Type: application/json

{
  "profile_id": "romina-remote-spanish-hr",
  "action": "not_relevant",
  "reason_codes": ["closed"],
  "notes": "La plataforma confirmó que la búsqueda cerró."
}
```

Supported actions are `interested`, `not_relevant`, and `applied`.
`not_relevant` requires at least one structured reason. Reason codes include
`not_remote`, `cannot_hire_argentina`, `requires_advanced_english`,
`closed`, `junior_or_internship`, `wrong_role`,
`english_description_or_application`, `duplicate`, `broken_link`, and
`other`.


## Quality Review Worker

When enable_quality_review is true (the default), every new result that is
persisted with presented=true receives exactly one versioned quality review for
the configured rubric. Rejects, unverified maybes, repeats, and overflow
results never receive a review event.

The API writes the review and a matching outbox record in the same database
transaction. After the Radar run commits, it makes a best-effort delivery of
pending outbox records to SQS. A second Lambda using
app.radar.quality.dispatch_handler is scheduled by EventBridge every five
minutes to retry any undelivered outbox records.

The SQS consumer is app.radar.quality.handler, packaged by
Dockerfile.quality-worker. Configure its SQS event source with
ReportBatchItemFailures, a DLQ, and a visibility timeout longer than the Lambda
timeout. The worker claims a short database lease before invoking Bedrock, so
duplicate SQS deliveries do not create duplicate model calls.

Required production configuration:

- RADAR_QUALITY_REVIEW_QUEUE_URL
- RADAR_QUALITY_REVIEW_MODEL_ID
- RADAR_QUALITY_REVIEW_BEDROCK_REGION (defaults to sa-east-1)
- database configuration already used by the API and workers

The reviewer is a bounded LangGraph workflow: validate immutable input,
evaluate with Bedrock, validate the structured result, and persist it. It has
no browser, database, or external action tools. Its stored result contains
pending/completed status, up/down verdict, score, confidence, rationale, risks,
evidence, and rubric version. The history endpoint returns it as
quality_review on each presented opportunity card.

## Persistence and Migration

Radar data is stored in:

- `radar_runs`
- `radar_opportunities`
- `radar_evaluations`
- `radar_feedback`

Apply migrations with:

```bash
uv run alembic upgrade head
```

Previously presented opportunities are suppressed from later remote runs but
remain available through the opportunity-history endpoint. Rejected and
unverified results are retained as evaluation evidence so classification
quality can be inspected and improved without showing noisy results to Romina.

## Local Development

Run the deterministic sample source:

```bash
uv run python -m app.radar --profile peter-latam-remote-ai-fullstack-product --source sample
```

Run Romina's live remote search after configuring `TAVILY_API_KEY`:

```bash
uv run python -m app.radar --profile romina-remote-spanish-hr --source tavily --limit 25
```

Run tests and lint:

```bash
uv run pytest
uv run ruff check app migrations tests
```
