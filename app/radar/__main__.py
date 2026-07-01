from __future__ import annotations

import argparse
import json
from typing import Sequence

from app.radar.connectors.base import DiscoveryConnector
from app.radar.connectors.greenhouse import GreenhouseConnector
from app.radar.connectors.lever import LeverConnector
from app.radar.connectors.sample import SampleConnector
from app.radar.connectors.tavily import TavilyConnector
from app.radar.discovery import run_discovery
from app.radar.profiles import PROFILES, get_profile


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the job radar discovery pipeline.")
    parser.add_argument(
        "--profile",
        default="peter-us-remote-direct-product",
        choices=sorted(PROFILES),
        help="Radar search profile to use.",
    )
    parser.add_argument(
        "--source",
        action="append",
        choices=["sample", "tavily", "greenhouse", "lever"],
        default=None,
        help="Discovery source. Can be passed more than once.",
    )
    parser.add_argument("--limit", type=int, default=25, help="Maximum discoveries.")
    parser.add_argument(
        "--greenhouse-board",
        action="append",
        default=[],
        help="Greenhouse board token, for example a company slug.",
    )
    parser.add_argument(
        "--lever-company",
        action="append",
        default=[],
        help="Lever company site slug, for example a company slug.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full result as JSON instead of a compact table.",
    )
    args = parser.parse_args(argv)

    profile = get_profile(args.profile)
    connectors = _build_connectors(
        sources=args.source or ["sample"],
        greenhouse_boards=args.greenhouse_board,
        lever_companies=args.lever_company,
    )
    result = run_discovery(profile=profile, connectors=connectors, limit=args.limit)

    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        _print_summary(result)
    return 0


def _build_connectors(
    sources: list[str], greenhouse_boards: list[str], lever_companies: list[str]
) -> list[DiscoveryConnector]:
    connectors: list[DiscoveryConnector] = []
    for source in sources:
        if source == "sample":
            connectors.append(SampleConnector())
        elif source == "tavily":
            connectors.append(TavilyConnector())
        elif source == "greenhouse":
            if not greenhouse_boards:
                raise ValueError("--greenhouse-board is required for source=greenhouse")
            connectors.append(GreenhouseConnector(greenhouse_boards))
        elif source == "lever":
            if not lever_companies:
                raise ValueError("--lever-company is required for source=lever")
            connectors.append(LeverConnector(lever_companies))
    return connectors


def _print_summary(result) -> None:
    print(
        json.dumps(
            {
                "profile_id": result.profile_id,
                "total_raw": result.total_raw,
                "total_unique": result.total_unique,
            },
            indent=2,
        )
    )
    for item in result.items:
        candidate = item.candidate
        classification = item.classification
        print(
            "\n"
            f"[{classification.verdict}] {classification.score}/100 "
            f"{candidate.title or '(untitled)'}"
        )
        print(f"Company: {candidate.company_name or '(unknown)'}")
        print(f"Location: {candidate.location_text or '(unknown)'}")
        print(f"Source: {candidate.source} | {candidate.canonical_url}")
        if classification.reasons:
            print(f"Why: {'; '.join(classification.reasons)}")


if __name__ == "__main__":
    raise SystemExit(main())

