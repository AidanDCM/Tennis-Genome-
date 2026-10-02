"""Report ATP player-ID corroboration from retained same-match evidence; no API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennis_genome.research_workbench.sportradar_identity_overlap import (
    corroborate_overlap_identities,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--canonical-csv", required=True, type=Path)
    parser.add_argument("--season-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    mapping = json.loads(args.season_map.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise ValueError("season map must be a JSON object")
    report = corroborate_overlap_identities(
        capture_root=args.capture_root,
        canonical_csv=args.canonical_csv,
        season_tournaments=mapping,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("identity report would overwrite an existing file")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "matched_events": report["matched_events"],
                "corroborated_players": report["corroborated_players"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
