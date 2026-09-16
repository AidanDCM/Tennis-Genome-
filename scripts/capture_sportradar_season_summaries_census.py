from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.sportradar_season_summaries_census_v2 import (
    capture_season_summaries_census,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the frozen historical Season Summaries call-budget census"
    )
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--access-level",
        choices=("trial", "production"),
        required=True,
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    census = capture_season_summaries_census(
        inventory_path=args.inventory,
        output_dir=args.output_dir,
        access_level=args.access_level,
        api_key=os.environ.get("SPORTRADAR_API_KEY", ""),
    )
    print(
        json.dumps(
            {
                "census_semantic_sha256": census.semantic_sha256,
                "historical_candidate_count": census.historical_candidate_count,
                "summaries_captured_count": census.summaries_captured_count,
                "history_not_available_count": census.history_not_available_count,
                "provider_request_count": census.provider_request_count,
                "total_raw_summary_count": census.total_raw_summary_count,
                "total_played_terminal_count": census.total_played_terminal_count,
                "total_walkover_count": census.total_walkover_count,
                "total_nonterminal_count": census.total_nonterminal_count,
                "total_required_timeline_count": census.total_required_timeline_count,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
