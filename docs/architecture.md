# Shared Backend Architecture

## Purpose and operating context

`job_search` is a shared Python/FastAPI backend for two frontend applications:

* `job_search_fe` uses the Direct Product Job Radar APIs.
* `151` uses the Crane Intelligence document and knowledge APIs.

Both clients currently have zero real production users. The project is primarily
an AWS learning environment, so architecture should stay simple, explicit,
secure, and pay-per-use. Do not add always-running infrastructure without a
specific product or learning objective.

## Client boundaries

| Client | Primary backend areas | Important boundary |
| --- | --- | --- |
| `job_search_fe` | `/radar/*`, candidate profile APIs, Radar feedback | Search profiles and results are scoped to the Radar domain. |
| `151` | `/documents/*`, `/knowledge/*` | Server-side document credentials scope access by source application and tenant. |

The FastAPI application, PostgreSQL database, deployment image repository,
CloudFormation stack, and common configuration are shared. Treat changes to
public routes, CORS, authentication, database models, or AWS IAM policies as
cross-client changes unless their scope is demonstrably isolated.

## AWS deployment shape

The `job-search-lambda` CloudFormation stack in `sa-east-1` deploys the shared
backend using on-demand Lambda functions and ECR images:

```text
browser clients
  -> Lambda Function URL / FastAPI API
  -> Neon PostgreSQL

document upload completion
  -> SQS document-processing worker
  -> S3 and Bedrock

EventBridge (opt-in; every five minutes when enabled)
  -> Crane knowledge-sync worker
```

The quality-review worker follows the same asynchronous pattern: the API writes
a durable outbox record, SQS delivers a small review identifier, and a worker
loads the immutable snapshot from PostgreSQL before calling Bedrock.

Crane knowledge-sync polling and Radar quality-review dispatch/consumption are
disabled by default through separate CloudFormation opt-in parameters. This
allows Neon to suspend while the applications are unused. Disabling these
triggers pauses RAG reconciliation and quality reviews without disabling the
shared API or document-processing worker. See the optional background processing
section in deploy/README.md for enablement and backlog behavior.

## Change checklist

Before modifying shared behavior, check:

1. Which client owns and calls the affected API route?
2. Does the change alter CORS, authentication, tenant scope, or database data?
3. Does the CloudFormation template and GitHub deployment workflow need to
   change with the application code?
4. Does the change add a recurring or always-on AWS cost?

See `deploy/README.md` for deployment and operational details.
