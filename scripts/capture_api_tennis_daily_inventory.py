from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_daily_inventory import (
    capture_api_tennis_daily_inventory,
)


def build(*, schedule_date: date, output_dir: Path) -> dict[str, object]:
    raw, filtered, manifest = capture_api_tennis_daily_inventory(
        schedule_date=schedule_date,
        api_key=os.environ.get("API_TENNIS_API", ""),
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "raw-fixtures.json").write_bytes(raw)
    (output_dir / "atp-wta-singles.json").write_bytes(filtered)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one complete API-Tennis daily fixture inventory"
    )
    parser.add_argument("--schedule-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build(
        schedule_date=args.schedule_date,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
