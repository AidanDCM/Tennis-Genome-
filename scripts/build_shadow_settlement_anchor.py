from __future__ import annotations

import argparse
import json
from pathlib import Path

MARKER = "<!-- TENNIS-GENOME-CHALLENGER-SHADOW-SETTLEMENT-V1 -->"
SCHEMA_VERSION = "tennis-genome-challenger-shadow-settlement-anchor-v1"


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def build_anchor_payload(
    *,
    manifest: dict[str, object],
    workflow_run_id: int,
    workflow_source_sha: str,
    settlement_ledger_issue: int,
) -> dict[str, object]:
    if workflow_run_id <= 0 or settlement_ledger_issue <= 0:
        raise ValueError("workflow run and ledger issue IDs must be positive")
    if len(workflow_source_sha) != 40:
        raise ValueError("workflow source SHA must be a 40-character commit SHA")
    return {
        "schema_version": SCHEMA_VERSION,
        "repository": "AidanDCM/Tennis-Genome-",
        "settlement_ledger_issue": settlement_ledger_issue,
        "workflow_run_id": workflow_run_id,
        "workflow_source_sha": workflow_source_sha,
        "source_shadow_artifact_id": manifest["source_shadow_artifact_id"],
        "source_prediction_artifact_id": manifest["source_prediction_artifact_id"],
        "verified_settlement_artifact_id": manifest["verified_settlement_artifact_id"],
        "verified_settlement_dossier_sha256": manifest[
            "verified_settlement_dossier_sha256"
        ],
        "match_id": manifest["match_id"],
        "winner_player_id": manifest["winner_player_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "shadow_anchor_comment_ids": manifest["shadow_anchor_comment_ids"],
        "finalization_bundle_sha256": manifest["finalization_bundle_sha256"],
        "settlement_sha256": manifest["settlement_sha256"],
        "failure_atlas_sha256": manifest["failure_atlas_sha256"],
        "league_table": manifest["league_table"],
    }


def render_anchor_body(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return f"{MARKER}\n```json\n{canonical}\n```"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build trusted shadow settlement anchor")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-source-sha", required=True)
    parser.add_argument("--settlement-ledger-issue", type=int, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-body", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = build_anchor_payload(
        manifest=_load_object(args.manifest),
        workflow_run_id=args.workflow_run_id,
        workflow_source_sha=args.workflow_source_sha,
        settlement_ledger_issue=args.settlement_ledger_issue,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output_body.write_text(render_anchor_body(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
