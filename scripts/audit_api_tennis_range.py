from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_range_probe import (
    capture_api_tennis_range_probe,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture one bounded API-Tennis fixture range")
    parser.add_argument("--date-start", required=True)
    parser.add_argument("--date-stop", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    audit = capture_api_tennis_range_probe(
        date_start=args.date_start,
        date_stop=args.date_stop,
        api_key=os.environ.get("API_TENNIS_API", ""),
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "probe_id": audit.probe_id,
                "date_start": audit.date_start,
                "date_stop": audit.date_stop,
                "span_days": audit.span_days,
                "provider_request_count": audit.provider_request_count,
                "fixture_count": audit.fixture_count,
                "atp_singles_count": audit.atp_singles_count,
                "wta_singles_count": audit.wta_singles_count,
                "finished_count": audit.finished_count,
                "pointbypoint_nonempty_count": audit.pointbypoint_nonempty_count,
                "statistics_nonempty_count": audit.statistics_nonempty_count,
                "response_bytes": audit.response_bytes,
                "raw_response_sha256": audit.raw_response_sha256,
                "audit_semantic_sha256": audit.semantic_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
