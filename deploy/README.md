# Production Deployment

## AWS Resources

- Region: `sa-east-1`
- ECR repository: `job-search-api`
- Lambda function: `job-search-api`
- CloudFormation stack: `job-search-lambda`
- Lambda log group: `/aws/lambda/job-search-api` with 14-day retention
- Function URL: read from the `FunctionUrl` stack output

The backend runs on demand and is not attached to a VPC. This avoids an
always-running load balancer, Fargate task, NAT gateway, and public IPv4
addresses. The account's current regional concurrency quota is 10, which caps
parallel Lambda executions. AWS requires all 10 slots to remain unreserved at
this quota, so a function-level reserved concurrency of one cannot be
configured unless the account quota is raised above its current value.

`TAVILY_API_KEY` remains in AWS Secrets Manager. CloudFormation resolves the
secret into the Lambda environment during deployment; secret values are never
stored in this repository.

The retired ECS Express configuration and verified shutdown record are under
`deploy/archive/`. `deploy/ecs-task-definition.json` is retained only as a
historical reconstruction aid.

## Automatic Deployments

`.github/workflows/deploy.yml` runs for every push to `main`:

1. Install the frozen dependency set from `uv.lock`.
2. Run Ruff and Pytest.
3. Obtain temporary AWS credentials through GitHub OIDC.
4. Build `Dockerfile.lambda` for Linux x86_64 without a provenance manifest.
5. Push the immutable commit-SHA image to ECR.
6. update the Lambda function to the new image and wait for completion;
7. verify the Function URL health endpoint and frontend CORS preflight.

The workflow can also be started manually from GitHub's Actions tab. Production
deployments are serialized so two image updates cannot run concurrently.

The IAM role is `job-search-github-deploy`. Its trust and least-privilege
deployment policy are stored under `deploy/iam/`.

## Initial Infrastructure Deployment

The initial Lambda resources are defined in `deploy/lambda-template.yaml`.
Deploy the stack with an immutable ECR image URI and the
`CAPABILITY_NAMED_IAM` capability. Subsequent application deployments update
only the function image through GitHub Actions.

The Function URL uses public `NONE` authentication so the browser frontend can
call it directly. CORS allows the stable production frontend origin and this
project's deployment URLs under the `petermoyanos-projects.vercel.app` scope;
unrelated Vercel projects remain blocked. CORS is
not authentication. Before adding multiple users or valuable paid operations,
place an authenticated API layer in front of the function or proxy requests
through an authenticated server-side frontend route.

## Monitoring and Rollback

Use Lambda metrics and `/aws/lambda/job-search-api` logs to inspect invocations,
errors, duration, throttling, and cold starts. The function timeout is five
minutes; the current regional account concurrency quota is 10.

See [`docs/observability.md`](../docs/observability.md) for the console paths,
Live Tail instructions, CLI command, event names, and example Logs Insights
queries.

Every deployment uses an immutable Git SHA image tag. To roll back, update the
function code to a previously known-good ECR image URI and wait for the function
update to complete.

## Document Ingestion P0

CloudFormation also owns the private document-ingestion resources:

- an automatically named S3 bucket with public access blocked, AES-256
  server-side encryption, bucket-owner-enforced object ownership, suspended
  versioning for this early-stage environment, and a short retention policy;
- least-privilege Lambda access to PUT and inspect only the `documents/*`
  prefix;
- one generated Secrets Manager client credential for `job-search` and one
  for `crane-intelligence`;
- Lambda environment configuration for the bucket, the 20 MiB limit, the
  15-minute presigned URL lifetime, and the secret ARNs.

The `/documents/*` endpoints require `Authorization: Bearer <client-secret>`.
The client secret is intended only for a Next.js Route Handler or another
server-side caller. It must never use a `NEXT_PUBLIC_*` variable. Each secret
contains its allowed `source_app` and tenant list, so requests and reads are
always scope-filtered.

The upload client must send every header returned in `required_headers` with
the presigned PUT. P0 signs and later verifies both `Content-Type:
application/pdf` and `x-amz-meta-document-id`.

The production application uses Neon's pooled URL from
`/job-search/database-url`. Run Alembic migrations with a direct Neon
connection, as recommended for schema operations, before deploying application
code that depends on a new revision:

```bash
DATABASE_URL='<direct-postgres-url>' uv run alembic upgrade head
```

Secret values can be read by authorized operators from the two secret ARNs in
the stack outputs; values are never emitted by CloudFormation or committed to
Git.

## Resume profile apply P1C

The private `job-search` credential also protects:

- `GET /profiles/{profile_id}/resume-documents`, which restores recent
  uploads for one authorized profile;
- `POST /resume-profile-drafts/{draft_id}/apply`, which applies only the
  explicitly selected sections of a completed draft.

Resume data is stored under `professional_profile` in the existing
`radar_profile_configs.profile_json`; no parallel profile identity is
created. Only a selected professional summary is also synchronized to
`candidate_summary`. Role tiers, sources, source priority, blocked domains,
queries, offer/application language, location policy, salary, eligibility, and
Radar execution settings are preserved verbatim. The profile revision is
checked optimistically, and `applied_at` is updated in the same transaction.

Skills merge case-insensitively; languages merge by language; certifications
merge by name and issuer; selected experience and education replace their own
professional sections after deduplication. Applying the same draft again is
data-idempotent.


## Document Preprocessing P1A

A verified upload is explicitly enqueued by `complete-upload`; S3 events are not
used. The queue payload is limited to `{"version":1,"document_id":"<uuid>"}`.
The worker always reloads bucket, key, tenant, source application, expected size,
and policy from PostgreSQL.

CloudFormation owns:

- an encrypted standard processing queue with a 360-second visibility timeout;
- an encrypted dead-letter queue with 14-day retention and a redrive threshold
  of three receives;
- the `job-search-document-processor` Lambda and its 14-day log group;
- a batch-size-five SQS event source configured with
  `ReportBatchItemFailures`;
- separate least-privilege worker IAM for SQS consumption, the document S3
  prefix, CloudWatch logs, and the existing database URL SSM parameter.

The API records `processing_enqueued_at` while holding the document row lock.
A queue error rolls the database transaction back and returns HTTP 503, so a
client retry can enqueue safely. A completed retry with an enqueue timestamp
does not publish another message. Because SQS Standard remains at-least-once,
the worker also atomically claims only `UPLOADED` rows. Recent
`PROCESSING` duplicates are acknowledged without reading S3; a processing
lease allows a message redelivered after a hard timeout to reclaim stale work.

The worker validates actual object length, configured and declared sizes,
object metadata, and the `%PDF-` signature before calculating SHA-256.
Permanent document errors become `FAILED` and are acknowledged. S3/database
infrastructure failures release the row back to `UPLOADED` where possible and
return the message identifier as a partial batch failure. SQS then retries it
and eventually moves repeated failures to the DLQ.

The production workflow builds two immutable images in the existing ECR
repository:

- `<git-sha>` from `Dockerfile.lambda` for FastAPI and Lambda Web Adapter;
- `<git-sha>-worker` from `Dockerfile.worker` for the native Lambda handler.

Both runtime Lambdas use Neon's pooled URL from SSM. Alembic continues to use a
direct Neon URL for schema operations. Pytest forces SQLite in memory before
importing application sessions so a developer's local `.env` can never make
the test suite mutate Neon.

## Crane Intelligence Knowledge Base P1B

CloudFormation declares a self-managed Amazon Bedrock Knowledge Base for
`crane-intelligence` documents under
`documents/<creactis-tenant>/crane-intelligence/`. It uses the existing
private document bucket, a retained S3 Vectors bucket and 1,024-dimension
float32/cosine index, and `cohere.embed-multilingual-v3` for Spanish and
English semantic search.

The Bedrock role can read only that tenant/source prefix, invoke only the
configured embedding model, and operate only the declared vector index. Neither
the document bucket nor the vector bucket is public. The resources are retained
if the stack is removed to prevent accidental loss of indexed content.

Deploying this template creates the knowledge base, source configuration, and
the `job-search-knowledge-sync` Lambda scheduled by EventBridge every five
minutes. The document worker writes each validated Crane PDF sidecar and
explicitly requests an idempotent source sync; it can write only that source
prefix and start only this Knowledge Base. The scheduled Lambda can read only
the database URL parameter and start or inspect jobs for this Knowledge Base.
It promotes a document to `RAG_INDEXED` only when Bedrock reports `COMPLETE`;
a `FAILED` or `STOPPED` job remains outside retrieval with a safe database
error. The deployment workflow publishes the existing `<git-sha>-worker`
image to both native handlers. The API Lambda has `bedrock:Retrieve` only
against this Knowledge Base; its authenticated `POST /knowledge/retrieve`
route derives tenant and source filters from the credential and never returns
S3 locations. Keep the model and the 1,024 vector dimensions aligned if either
is changed.

## Radar Quality Review P1

CloudFormation owns an encrypted SQS quality-review queue and retained DLQ, the
`job-search-quality-review-worker` SQS consumer, and the
`job-search-quality-review-dispatcher` EventBridge target. The dispatcher
runs every five minutes to deliver pending database-outbox records; it does not
keep a Lambda running between invocations.

Only `presented=true` Radar opportunities are staged. The API may enqueue them
after a successful run, while the dispatcher provides durable retry. The worker
has only database-parameter read access, queue consume access, and
`bedrock:InvokeModel` for the configured review model. The dispatcher can only
read the database parameter and send to this queue.

The deployment workflow builds a third immutable image,
`<git-sha>-quality-review`, from `Dockerfile.quality-worker`, then updates both
quality-review functions.
