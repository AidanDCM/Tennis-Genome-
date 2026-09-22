from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.web_shadow_wta_intake_core import build_wta_web_shadow_intake

__all__ = ["build_wta_web_shadow_intake"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic model-blind Web Shadow slate from retained "
            "official WTA API JSON"
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("web-shadow/intake-config.json"),
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--snapshot-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build_wta_web_shadow_intake(
        config_path=args.config,
        source_root=args.source_root,
        repo_root=args.repo_root,
        observed_at=args.observed_at,
        snapshot_id=args.snapshot_id,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
