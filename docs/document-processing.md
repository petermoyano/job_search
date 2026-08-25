# Document processing

The `documents` bounded context owns upload, storage, asynchronous delivery,
authorization, state, and processing-policy dispatch. It does not depend on Radar
profiles, jobs, or opportunities.

## Resume policy (P1B)

The intelligent workflow is enabled only for:

- `source_app=job-search`
- `processing_policy=resume`

It extracts text locally with `pypdf`, preserving page markers and sending at
most `RESUME_MAX_MODEL_INPUT_CHARACTERS` characters to Amazon Bedrock. Scanned
or textless PDFs fail permanently with `PDF_TEXT_NOT_EXTRACTABLE`; OCR remains
out of scope.

Amazon Bedrock uses `mistral.ministral-3-14b-instruct` in `sa-east-1` by default.
The worker makes one JSON-Schema-constrained classification call and only makes a
second extraction call after deterministic acceptance. Pydantic validates both
responses again.
Output collection sizes are bounded and an output-token truncation becomes a
safe permanent failure instead of persisting partial JSON.

Default classification rules are:

- `is_resume=true` and confidence at least `0.80`: `ACCEPTED`
- confidence at most `0.40`, or `is_resume=false` with confidence at least
  `0.80`: `REJECTED`
- all other outcomes: `NEEDS_REVIEW`

The thresholds, model, text limits, and Bedrock region are environment-driven.

## Persistence and API

`documents.context` may contain a validated optional `profile_id` for the
job-search resume policy. The extracted value is stored in
`resume_profile_drafts` with a unique `document_id`, schema version, model ID,
and extraction timestamp. It never updates `candidate_profiles` or
`radar_profile_configs`.

Authorized clients can use:

- `GET /documents/{document_id}` for state, classification, decision, and result
  identifiers.
- `GET /documents/{document_id}/result` for the validated resume draft.

Both queries retain the existing tenant and source-app scope.

## Retry and privacy behavior

Transient Bedrock, S3, and database failures are returned to SQS for retry.
Permanent PDF or model-output errors become `FAILED`. A unique document-to-draft
constraint prevents duplicate drafts, while `DATA_EXTRACTED` permits a retry to
finish `COMPLETED` without invoking the model again.

Document text, contact information, structured payloads, credentials, and signed
URLs are never logged. Logs contain only safe identifiers, state, model, duration,
character counts, and aggregate token usage.

## Deferred work

P1C should add an explicit, authorized apply-draft workflow with field-level
review and optimistic concurrency. OCR, frontend upload UI, human-review UI,
industrial policies, RAG, embeddings, and full transactional outbox semantics
remain intentionally deferred.
