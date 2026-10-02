"""Create a review-only identity report from retained local data; no API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennis_genome.research_workbench.sportradar_identity_candidates import (
    build_candidate_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--canonical-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = build_candidate_report(
        capture_root=args.capture_root, canonical_root=args.canonical_root
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("identity candidate report would overwrite an existing file")
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "provider_player_count": report["provider_player_count"],
                "counts": report["counts"],
                "authoritative_crosswalk": False,
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
