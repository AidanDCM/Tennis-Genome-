from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.sportradar_timeline_sample_capture import (
    capture_timeline_audit_sample,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the preregistered Sportradar historical Timeline audit sample"
    )
    parser.add_argument("--sample-plan", required=True, type=Path)
    parser.add_argument("--census", required=True, type=Path)
    parser.add_argument("--census-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--access-level", choices=("trial", "production"), required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    api_key = os.environ.get("SPORTRADAR_API_KEY", "")
    capture = capture_timeline_audit_sample(
        sample_plan_path=args.sample_plan,
        census_path=args.census,
        census_root=args.census_root,
        output_dir=args.output_dir,
        repo_root=args.repo_root,
        access_level=args.access_level,
        api_key=api_key,
    )
    print(
        json.dumps(
            {
                "capture_semantic_sha256": capture.semantic_sha256,
                "provider_request_count": capture.provider_request_count,
                "selected_timeline_count": capture.selected_timeline_count,
                "captured_timeline_count": capture.captured_timeline_count,
                "history_not_available_count": capture.history_not_available_count,
                "admitted_season_count": capture.admitted_season_count,
                "rejected_season_count": capture.rejected_season_count,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
