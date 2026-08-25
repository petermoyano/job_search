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
language. Component identifier and human-friendly title are optional. The
worker will later write an `original.pdf.metadata.json` S3 sidecar with these
filterable fields: tenant_id, source_app, project_id, asset_id, component_id,
document_type, and language.

## Retrieval contract

The future authenticated `POST /knowledge/retrieve` accepts a normalized
question, optional project/asset/component filters, and one to eight results.
Tenant and source filters are added by the backend from the credential. The
response exposes document ID, title, excerpt, score, and optional page number;
it never exposes a private S3 URI.

## Lifecycle

```
PENDING_UPLOAD -> UPLOADED -> PROCESSING -> PREPROCESSED -> RAG_INDEXED
```

Bedrock ingestion jobs are global to the S3 data source. A later sync-run record
will store the Bedrock job ID, cutoff, status, counters, and errors. A document
is RAG_INDEXED only after a successful job that includes it.

## Chat behavior

The Next.js route will retrieve server-to-server. Retrieved text is untrusted
reference material and remains delimited in the model prompt. Structured live
asset data remains authoritative for operational status and maintenance.
