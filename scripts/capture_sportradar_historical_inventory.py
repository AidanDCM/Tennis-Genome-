from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.sportradar_inventory_capture import (
    capture_historical_season_inventory,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture the frozen Sportradar ATP/WTA historical season inventory"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--access-level",
        choices=("trial", "production"),
        required=True,
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    api_key = os.environ.get("SPORTRADAR_API_KEY", "")
    receipt = capture_historical_season_inventory(
        output_dir=args.output_dir,
        access_level=args.access_level,
        api_key=api_key,
    )
    manifest = json.loads(
        (args.output_dir / "manifest.json").read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "capture_receipt_sha256": receipt.semantic_sha256,
                **manifest,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
