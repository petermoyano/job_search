# Naive RAG contract

## Scope

The first knowledge base serves Crane Intelligence documents only.

- source application: `crane-intelligence`
- initial tenant: `creactis`
- processing policy: `knowledge-base`
- document source: the existing private S3 document bucket
- vector store: Amazon S3 Vectors through Amazon Bedrock Knowledge Bases

The API credential remains the authority for tenant and source. A caller must
never select a different tenant or source in a retrieval request.

## Document metadata

A knowledge document requires a project, asset identifier, document type, and
language. Component identifier and human-friendly title are optional. After the
PDF signature and SHA-256 are validated, the worker writes the private
`original.pdf.metadata.json` S3 sidecar next to the PDF. It includes document,
tenant, source, project, asset, component, document type, title, language, and
SHA-256 metadata. The sidecar is deliberately smaller than Bedrock’s 10 KiB
limit and metadata is filterable without exposing the S3 URI.

## Retrieval contract

The future authenticated `POST /knowledge/retrieve` accepts a normalized
question, optional project/asset/component filters, and one to eight results.
Tenant and source filters are added by the backend from the credential. The
response exposes document ID, title, excerpt, score, and optional page number;
it never exposes a private S3 URI.

## Lifecycle

```
PENDING_UPLOAD -> UPLOADED -> PROCESSING -> PREPROCESSED -> RAG_INDEXED
                                 |
                                 +-> knowledge_sync_status: PENDING | IN_PROGRESS
```

Bedrock ingestion jobs are global to the S3 data source. The worker uses a
deterministic client token, persists the returned job ID when one is available,
and records `PENDING` when another source-wide sync is already active. The
`job-search-knowledge-sync` Lambda runs every five minutes: it retries
pending requests, polls active jobs, and sets `RAG_INDEXED` only after Bedrock
reports `COMPLETE`. A `FAILED` or `STOPPED` job remains out of retrieval,
records a safe error, and is visible as `knowledge_sync_status=FAILED`.

## Chat behavior

The Next.js route will retrieve server-to-server. Retrieved text is untrusted
reference material and remains delimited in the model prompt. Structured live
asset data remains authoritative for operational status and maintenance.
