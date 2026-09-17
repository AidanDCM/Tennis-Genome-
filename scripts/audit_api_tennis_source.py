from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_source_audit import (
    capture_api_tennis_source_probe,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the one-request API-Tennis source-admission probe"
    )
    parser.add_argument("--date", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    audit = capture_api_tennis_source_probe(
        requested_date=args.date,
        api_key=os.environ.get("API_TENNIS_API", ""),
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "probe_id": audit.probe_id,
                "audit_semantic_sha256": audit.semantic_sha256,
                "provider_request_count": audit.provider_request_count,
                "fixture_count": audit.fixture_count,
                "atp_singles_count": audit.atp_singles_count,
                "wta_singles_count": audit.wta_singles_count,
                "pointbypoint_nonempty_count": audit.pointbypoint_nonempty_count,
                "statistics_nonempty_count": audit.statistics_nonempty_count,
                "separate_actual_start_field_paths": list(
                    audit.separate_actual_start_field_paths
                ),
                "historical_actual_start_admissible": (
                    audit.historical_actual_start_admissible
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
