# Production observability

The production FastAPI application writes standard Python logs to the Lambda
log group `/aws/lambda/job-search-api` in `sa-east-1`. CloudWatch retains the
group for 14 days.

## AWS console

Use either of these paths:

1. **Lambda** → **Functions** → `job-search-api` → **Monitor** →
   **View CloudWatch logs**.
2. **CloudWatch** → **Logs** → **Log groups** →
   `/aws/lambda/job-search-api`.

CloudWatch **Live Tail** is the closest equivalent to watching Vercel's live
production logs. **Logs Insights** is more useful for searching older events.

Useful Logs Insights queries:

```text
fields @timestamp, @message
| filter @message like /event=radar_run_committed/
| sort @timestamp desc
| limit 50
```

```text
fields @timestamp, @message
| filter @message like /event=radar_history_loaded|event=radar_feedback_saved/
| sort @timestamp desc
| limit 100
```

```text
fields @timestamp, @message
| filter @message like /event=http_request_failed/ or @message like /ERROR/
| sort @timestamp desc
| limit 100
```

Every non-health HTTP response includes an `X-Request-ID` header. Supply that
same header from a client to correlate a frontend action with the corresponding
`http_request_started` and `http_request_completed` events.

The application logs operational metadata and counts, but intentionally does
not log database credentials, API keys, feedback notes, or complete vacancy
payloads.

## AWS CLI

Follow the production stream from Windows PowerShell:

```powershell
aws logs tail /aws/lambda/job-search-api `
  --region sa-east-1 `
  --follow `
  --format short
```

Stop the live stream with `Ctrl+C`.
