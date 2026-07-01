# Radar Module

The radar module is the first implementation of the job discovery side of this
project. The existing backend is good at analyzing a job lead once we already
have it. This module focuses on the missing earlier step: finding likely direct
product opportunities before they enter the main analysis workflow.

The initial target profile is `peter-latam-remote-ai-fullstack-product`:
fully remote, LATAM-friendly or globally remote direct employer roles at product
companies, especially AI Engineer, Applied AI, full-stack product engineering,
and ownership-heavy roles.

## Current Scope

This is intentionally a local-first module. It does not add database tables,
migrations, or FastAPI endpoints yet. The goal is to test source quality and
classification behavior from the terminal before committing to a persistent
schema or UI.

Run the sample pipeline:

```bash
uv run python -m app.radar
```

The command logs progress to stderr by default. Use `--log-level DEBUG`,
`--log-level INFO`, `--log-level WARNING`, or `--log-level ERROR` to control
how much progress detail is shown.

Print full JSON:

```bash
uv run python -m app.radar --json
```

Use Tavily after setting TAVILY_API_KEY in .env or exporting it in your shell:

```bash
uv run python -m app.radar --source tavily --limit 25
```

Use known ATS boards directly:

```bash
uv run python -m app.radar --source greenhouse --greenhouse-board exampleco
uv run python -m app.radar --source lever --lever-company exampleco
```

## Structure

`models.py`
: Shared Pydantic models for search profiles, raw discoveries, normalized job
candidates, classifications, and discovery run results.

`profiles.py`
: Saved radar profiles. The first profile encodes Peter's current search:
AI/full-stack direct product roles that are fully remote and open to LATAM,
Argentina, Americas, global remote, or anywhere candidates.

`connectors/`
: Source-specific discovery connectors. The module currently includes:

- `sample.py`: local deterministic examples for development and tests.
- `tavily.py`: web search connector for query-based discovery.
- `greenhouse.py`: direct Greenhouse job board connector.
- `lever.py`: direct Lever postings connector.

`normalize.py`
: Converts source-specific raw discoveries into one internal candidate shape
and canonicalizes URLs for deduplication.

`dedupe.py`
: Removes repeated candidates, primarily by canonical URL.

`classify.py`
: A deterministic first-pass classifier. It looks for direct employer signals,
US-compatible remote signals, product-company signals, target role matches, and
reject terms such as staffing, hidden clients, consulting, onsite, or hybrid
constraints. This is not meant to replace Bedrock; it is a cheap filter before
LLM classification.

`discovery.py`
: Orchestrates the full pipeline:

```text
connectors -> raw discoveries -> normalization -> dedupe -> classification
```

`__main__.py`
: CLI entrypoint for running discovery locally.

## Why No Database Yet?

The source strategy is still the riskiest part of the product. Before adding
tables and API endpoints, we need to learn:

- Which sources return real direct product jobs.
- Which queries produce too much staffing or repost noise.
- Which ATS boards are worth tracking directly.
- Which fields are required for useful review and deduplication.

Once this loop is useful, the next step is to persist discoveries and add a
review inbox.

## Next Steps

1. Run the sample pipeline and inspect the JSON shape.
2. Add a Tavily key and test the default search profile.
3. Start a small curated list of real Greenhouse and Lever company slugs.
4. Compare deterministic classification against your actual judgment.
5. Add a Bedrock classifier that returns structured evidence for:
   - direct employer vs staffing/intermediary
   - LATAM/global remote compatibility
   - product company fit
   - role fit
6. Persist discoveries and expose review endpoints:
   - `POST /radar/runs`
   - `GET /radar/discoveries`
   - `POST /radar/discoveries/{id}/promote`

The first success criterion is simple: one command should return a short,
ranked list of fresh opportunities worth manually reviewing.

