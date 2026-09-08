"""Merge real search-provider credentials using AWS CLI; never print values.

Run from the repository root:
    .venv/bin/python deploy/migrate_external_api_keys.py --profile job-search
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from dotenv import dotenv_values

SECRET_NAME = "job-search/external-api-keys"
KEYS = ("TAVILY_API_KEY", "SERPER_API_KEY", "SERPAPI_API_KEY", "RAPIDAPI_KEY")


def real_value(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.strip().lower()
        not in {"todo", "changeme", "placeholder", "your-api-key", "your_api_key"}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="job-search")
    parser.add_argument("--region", default="sa-east-1")
    args = parser.parse_args()
    base = ["aws", "--profile", args.profile, "--region", args.region, "--no-cli-pager"]

    def aws(*command: str, payload: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory(prefix="job-search-secret-") as directory:
            invocation = [*base, *command]
            if payload is not None:
                path = Path(directory) / "input.json"
                path.touch(mode=0o600)
                path.write_text(json.dumps(payload))
                invocation.extend(["--cli-input-json", f"file://{path}"])
            result = subprocess.run(
                invocation, capture_output=True, text=True, check=False
            )
            if result.returncode:
                # Provider/CLI error text may contain request data.
                raise RuntimeError("AWS CLI operation failed: " + command[1])
            return json.loads(result.stdout or "{}")

    listed = aws("secretsmanager", "list-secrets")
    exists = any(s["Name"] == SECRET_NAME for s in listed["SecretList"])
    original = (
        aws("secretsmanager", "get-secret-value", "--secret-id", SECRET_NAME)
        if exists
        else None
    )
    aggregate = json.loads(original["SecretString"]) if original else {}
    if not isinstance(aggregate, dict):
        raise RuntimeError("Aggregate secret must be a JSON object; no changes applied")

    # Only the job-search Tavily credential is read. Document credentials are
    # intentionally neither read nor migrated.
    old = aws(
        "secretsmanager", "get-secret-value", "--secret-id", "job-search/tavily-api-key"
    )
    tavily = old["SecretString"]
    try:
        parsed = json.loads(tavily)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        tavily = parsed.get("TAVILY_API_KEY") or parsed.get("api_key")
    if not real_value(tavily):
        raise RuntimeError("Existing Tavily secret is not a usable credential")
    candidates = {"TAVILY_API_KEY": tavily}
    for path in (".env", ".env.local", ".env.production"):
        if Path(path).is_file():
            values = dotenv_values(path)
            for key in KEYS[1:]:
                if real_value(values.get(key)):
                    candidates[key] = values[key]
    for key in KEYS[1:]:
        if real_value(os.environ.get(key)):
            candidates[key] = os.environ[key]

    added = []
    for key, value in candidates.items():
        if key not in aggregate:
            aggregate[key] = value
            added.append(key)

    if added:
        # Refuse to overwrite an aggregate that changed during this migration.
        if original:
            current = aws(
                "secretsmanager", "get-secret-value", "--secret-id", SECRET_NAME
            )
            if current["VersionId"] != original["VersionId"]:
                raise RuntimeError("Aggregate changed concurrently; rerun migration")
        payload = {"SecretString": json.dumps(aggregate)}
        payload["SecretId" if exists else "Name"] = SECRET_NAME
        aws(
            "secretsmanager",
            "put-secret-value" if exists else "create-secret",
            payload=payload,
        )
    verified = json.loads(
        aws("secretsmanager", "get-secret-value", "--secret-id", SECRET_NAME)[
            "SecretString"
        ]
    )
    if verified != aggregate:
        raise RuntimeError("Aggregate verification failed")
    print(
        json.dumps(
            {
                "secret": SECRET_NAME,
                "added_key_names": added,
                "present_provider_key_names": [
                    k for k in KEYS if real_value(verified.get(k))
                ],
                "old_tavily_secret": "unchanged",
            }
        )
    )


if __name__ == "__main__":
    main()
