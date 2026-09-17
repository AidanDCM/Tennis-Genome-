from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.sportradar_season_summaries_resume_v2 import (
    resume_season_summaries_census,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resume the frozen Sportradar Season Summaries census from retained evidence"
    )
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--partial-census-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--access-level", required=True, choices=("trial", "production"))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    census, checkpoint = resume_season_summaries_census(
        inventory_path=args.inventory,
        partial_census_root=args.partial_census_root,
        output_dir=args.output_dir,
        access_level=args.access_level,
        api_key=os.environ.get("SPORTRADAR_API_KEY", ""),
    )
    payload = {
        "status": "COMPLETE" if census is not None else "PAUSED_QUOTA",
        "checkpoint_semantic_sha256": checkpoint.semantic_sha256,
        "completed_candidate_count": checkpoint.completed_candidate_count,
        "historical_candidate_count": checkpoint.historical_candidate_count,
        "next_candidate_index": checkpoint.next_candidate_index,
        "next_season_id": checkpoint.next_season_id,
        "quota_exhausted": checkpoint.quota_exhausted,
        "retained_provider_response_count": checkpoint.retained_provider_response_count,
        "reusable_provider_response_count": checkpoint.reusable_provider_response_count,
        "census_semantic_sha256": None if census is None else census.semantic_sha256,
        "provider_request_count": None if census is None else census.provider_request_count,
        "total_required_timeline_count": (
            None if census is None else census.total_required_timeline_count
        ),
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
