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
  server-side encryption, bucket-owner-enforced object ownership, versioning,
  and a short retention policy for old noncurrent versions;
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
