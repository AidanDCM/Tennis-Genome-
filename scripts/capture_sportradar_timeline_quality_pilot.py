from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.sportradar_timeline_quality_capture import (
    capture_timeline_quality_pilot,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the preregistered Sportradar timeline quality pilot"
    )
    parser.add_argument("--sample-plan", required=True, type=Path)
    parser.add_argument("--census", required=True, type=Path)
    parser.add_argument("--census-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--access-level", required=True, choices=("trial", "production")
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = capture_timeline_quality_pilot(
        sample_plan_path=args.sample_plan,
        census_path=args.census,
        census_root=args.census_root,
        output_dir=args.output_dir,
        access_level=args.access_level,
        api_key=os.environ.get("SPORTRADAR_API_KEY", ""),
    )
    report_path = args.output_dir / "timeline-quality-pilot-report.json"
    report_file_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "report_semantic_sha256": report.semantic_sha256,
                "report_file_sha256": report_file_sha,
                "provider_request_count": report.provider_request_count,
                "selected_season_count": report.selected_season_count,
                "played_terminal_count": report.played_terminal_count,
                "exact_match_started_count": report.exact_match_started_count,
                "exact_coverage_rate": report.exact_coverage_rate,
                "conflicting_match_started_count": report.conflicting_match_started_count,
                "invalid_match_started_time_count": report.invalid_match_started_time_count,
                "pilot_disposition": report.pilot_disposition,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
