# Radar Module

The radar module is the first implementation of the job discovery side of this
project. The existing backend is good at analyzing a job lead once we already
have it. This module focuses on the missing earlier step: finding likely direct
product opportunities before they enter the main analysis workflow.

The radar now supports multiple search profiles. The default profile remains
`peter-latam-remote-ai-fullstack-product`: fully remote, LATAM-friendly or
globally remote direct employer roles at product companies, especially AI
Engineer, Applied AI, full-stack product engineering, and ownership-heavy roles.
It also includes two Romina profiles: `romina-remote-spanish-hr` for remote
Spanish-language HR roles, and `romina-mendoza-hr-onsite-hybrid` for Mendoza
or Gran Mendoza onsite/hybrid HR roles.

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
uv run python -m app.radar --profile romina-remote-spanish-hr --source tavily --limit 25
uv run python -m app.radar --profile romina-mendoza-hr-onsite-hybrid --source tavily --limit 25
```

Use known ATS boards directly:

```bash
uv run python -m app.radar --source greenhouse --greenhouse-board exampleco
uv run python -m app.radar --source lever --lever-company exampleco
```

## REST API

The FastAPI app exposes the radar for the frontend:

```bash
GET /radar/profiles
POST /radar/runs
```

Example run request:

```json
{
  "profile_id": "romina-mendoza-hr-onsite-hybrid",
  "source": "tavily",
  "limit": 25
}
```

Use `source: "sample"` for local UI testing without calling Tavily.

## Structure

`models.py`
: Shared Pydantic models for search profiles, raw discoveries, normalized job
candidates, classifications, and discovery run results.

`profiles.py`
: Saved radar profiles for each candidate/search intent. Peter's profile
targets remote AI/full-stack product roles. Romina has one remote Spanish HR
profile and one Mendoza onsite/hybrid HR profile. Her long list of job sites
is stored as `source_references` metadata for future source work, not scraped.

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
: A deterministic first-pass classifier. It keeps generic source quality
signals in code, then applies profile-specific positive and negative scoring
groups. This lets Peter's AI/product search and Romina's Spanish HR searches
use the same pipeline with different fit criteria. This is not meant to
replace Bedrock; it is a cheap filter before LLM classification.

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

