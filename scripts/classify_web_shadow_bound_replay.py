"""Classify a verified Web Shadow artifact against already frozen match IDs.

The caller must verify the downloaded ZIP against GitHub's artifact digest.
This precheck can skip a fully repeated run; it never freezes evidence.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def classify(manifest: dict, scorecard: dict, *, run_id: int, source_sha: str) -> dict:
    if manifest.get("schema_version") != "tennis-genome-web-shadow-bound-evidence-v1":
        raise ValueError("unexpected bound manifest schema")
    if manifest.get("production_eligible") is not False:
        raise ValueError("bound evidence must remain non-production")
    if manifest.get("workflow_run_id") != run_id:
        raise ValueError("bound workflow run ID mismatch")
    if manifest.get("workflow_source_sha") != source_sha:
        raise ValueError("bound workflow source SHA mismatch")
    if scorecard.get("schema_version") != "tennis-genome-web-shadow-scorecard-v1":
        raise ValueError("unexpected scorecard schema")
    results = manifest.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("bound results must be nonempty")
    if len(results) != manifest.get("predicted_target_count"):
        raise ValueError("bound prediction count mismatch")
    incoming = [row.get("match_id") if isinstance(row, dict) else None for row in results]
    if any(not isinstance(value, str) or not value for value in incoming):
        raise ValueError("bound result has missing match ID")
    if len(incoming) != len(set(incoming)):
        raise ValueError("bound result contains duplicate match IDs")
    existing = [
        row.get("match_id")
        for slate in scorecard.get("slates", [])
        for row in slate.get("predictions", [])
    ]
    if len(existing) != len(set(existing)):
        raise ValueError("scorecard already has duplicate match IDs")
    overlap = set(incoming) & set(existing)
    if overlap and len(overlap) != len(incoming):
        raise ValueError("bound slate mixes already-frozen and new match IDs")
    status = "FULLY_REPEATED" if overlap else "NEW"
    return {
        "status": status,
        "workflow_run_id": run_id,
        "incoming_match_count": len(incoming),
        "already_frozen_match_count": len(overlap),
        "new_match_count": len(incoming) - len(overlap),
        "match_ids": incoming,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.artifact_zip) as archive:
        manifest = json.loads(archive.read("bound-evidence-manifest.json"))
    scorecard = json.loads(args.scorecard.read_bytes())
    print(json.dumps(classify(manifest, scorecard, run_id=args.run_id, source_sha=args.source_sha)))


if __name__ == "__main__":
    main()
