from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.web_shadow_wta_acquisition_core import acquire_wta_sources


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch retained official WTA JSON for deterministic Web Shadow intake"
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("web-shadow/intake-config.json"),
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--manifest-out", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = acquire_wta_sources(
        config_path=args.config,
        source_root=args.source_root,
        observed_at=args.observed_at,
    )
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "index_count": len(manifest["index_records"]),
                "source_count": len(manifest["source_records"]),
                "manifest": args.manifest_out.as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
