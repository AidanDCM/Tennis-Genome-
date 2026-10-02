"""Run the bounded 2026 historical continuation capture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tennis_genome.research_workbench.sportradar_targeted_2026 import (
    capture_targeted_2026,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--access-level", choices=("trial", "production"), default="trial")
    parser.add_argument("--max-requests", type=int, required=True)
    args = parser.parse_args()
    result = capture_targeted_2026(
        inventory_path=args.inventory,
        output_dir=args.output_dir,
        source_dir=args.source_dir,
        access_level=args.access_level,
        api_key=os.environ.get("SPORTRADAR_API_KEY", ""),
        max_requests=args.max_requests,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
