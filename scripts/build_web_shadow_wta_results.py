from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.web_shadow_wta_result_core import build_wta_web_shadow_results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile retained official WTA finished rows into Web Shadow result evidence"
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("web-shadow/intake-config.json"),
    )
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=Path("web-shadow/scorecard.json"),
    )
    parser.add_argument("--acquisition-manifest", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--summary-out", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = build_wta_web_shadow_results(
        config_path=args.config,
        scorecard_path=args.scorecard,
        acquisition_manifest_path=args.acquisition_manifest,
        source_root=args.source_root,
        repo_root=args.repo_root,
        observed_at=args.observed_at,
        snapshot_id=args.snapshot_id,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(
            summary,
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
                "result_count": summary["result_count"],
                "pending_prediction_count": summary["pending_prediction_count"],
                "unresolved_prediction_count": summary["unresolved_prediction_count"],
                "unfinished_prediction_count": summary["unfinished_prediction_count"],
                "snapshot_id": summary["snapshot_id"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
