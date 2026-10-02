"""Audit retained Sportradar stats against pinned 2026 ATP CSV, offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennis_genome.research_workbench.sportradar_stat_overlap import audit_stat_overlap


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--season-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mapping = json.loads(args.season_map.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise ValueError("season map must be a JSON object")
    result = audit_stat_overlap(
        capture_root=args.capture_root,
        canonical_csv=args.canonical_csv,
        season_tournaments=mapping,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("overlap report would overwrite an existing file")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"total_counts": result["total_counts"], "output": str(args.output)}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
