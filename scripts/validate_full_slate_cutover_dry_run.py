from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennis_genome.prospective.full_slate_cutover import (
    assess_full_slate_cutover,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a nonpublishing Forward-004 full-slate dry run for cutover"
    )
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    assessment = assess_full_slate_cutover(
        args.artifact_root,
        expected_source_sha=args.expected_source_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(assessment.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(assessment.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
