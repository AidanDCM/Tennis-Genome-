from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_filtered_range import (
    capture_api_tennis_filtered_range,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture ATP/WTA singles from one bounded API-Tennis date range"
    )
    parser.add_argument("--date-start", required=True)
    parser.add_argument("--date-stop", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    audit = capture_api_tennis_filtered_range(
        date_start=args.date_start,
        date_stop=args.date_stop,
        api_key=os.environ.get("API_TENNIS_API", ""),
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "capture_id": audit.capture_id,
                "date_start": audit.date_start,
                "date_stop": audit.date_stop,
                "span_days": audit.span_days,
                "provider_request_count": audit.provider_request_count,
                "atp_fixture_count": audit.atp_fixture_count,
                "wta_fixture_count": audit.wta_fixture_count,
                "fixture_count": audit.event_key_count,
                "finished_fixture_count": audit.finished_fixture_count,
                "statistics_nonempty_count": audit.statistics_nonempty_count,
                "pointbypoint_nonempty_count": audit.pointbypoint_nonempty_count,
                "response_bytes_total": audit.response_bytes_total,
                "combined_raw_sha256": audit.combined_raw_sha256,
                "serve_return_input_sha256": audit.serve_return_input_sha256,
                "audit_semantic_sha256": audit.semantic_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
