from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.derive_web_shadow_elo_baseline import (
    finalize_elo_baseline_candidate,
)


_SCHEMA = "tennis-genome-web-shadow-bound-evidence-v1"
_RECEIPT_SCHEMA = "tennis-genome-web-shadow-slate-receipt-v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return payload


def _normalized_artifact_digest(value: str) -> str:
    digest = value.strip().lower()
    if digest.startswith("sha256:"):
        digest = digest.removeprefix("sha256:")
    if len(digest) != 64:
        raise ValueError("artifact SHA-256 must contain 64 hex characters")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ValueError("artifact SHA-256 must be hexadecimal") from exc
    return digest


def _artifact_path(root: Path, value: str, *, expected_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"artifact path must be relative: {value}")
    if path.parts[: len(expected_root.parts)] != expected_root.parts:
        raise ValueError(f"artifact path escaped expected root: {value}")
    resolved = root.parent / path
    if not resolved.is_file():
        raise FileNotFoundError(f"artifact file is missing: {value}")
    return resolved


def finalize_web_shadow_slate_evidence(
    *,
    slate_root: Path,
    source_reconciliation_path: Path,
    history_cache_receipt_path: Path,
    workflow_run_id: int,
    workflow_artifact_id: int,
    workflow_artifact_sha256: str,
    workflow_source_sha: str,
    output_root: Path,
) -> dict[str, Any]:
    manifest_path = slate_root / "slate-manifest.json"
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != "tennis-genome-web-shadow-slate-v2":
        raise ValueError("unsupported Web Shadow slate manifest schema")
    if manifest.get("production_eligible") is not False:
        raise ValueError("Web Shadow slate must remain non-production")

    eligible = int(manifest.get("eligible_target_count", -1))
    predicted = int(manifest.get("predicted_target_count", -1))
    skipped = int(manifest.get("skipped_target_count", -1))
    if eligible <= 0 or predicted < 0 or skipped < 0:
        raise ValueError("invalid Web Shadow slate denominator")
    if predicted + skipped != eligible:
        raise ValueError("predicted + skipped differs from slate denominator")

    results = manifest.get("results")
    if not isinstance(results, list) or len(results) != predicted:
        raise ValueError("slate result count differs from predicted target count")
    if workflow_run_id <= 0 or workflow_artifact_id <= 0:
        raise ValueError("workflow IDs must be positive")
    source_sha = workflow_source_sha.strip().lower()
    if len(source_sha) != 40:
        raise ValueError("workflow source SHA must contain 40 hex characters")
    try:
        int(source_sha, 16)
    except ValueError as exc:
        raise ValueError("workflow source SHA must be hexadecimal") from exc
    artifact_sha = _normalized_artifact_digest(workflow_artifact_sha256)

    committed_dates = set()
    seen_stems: set[str] = set()
    evidence_rows: list[dict[str, Any]] = []

    predictions_root = output_root / "predictions"
    baselines_root = output_root / "baselines"
    candidates_root = output_root / "baseline-candidates"
    predictions_root.mkdir(parents=True, exist_ok=True)
    baselines_root.mkdir(parents=True, exist_ok=True)
    candidates_root.mkdir(parents=True, exist_ok=True)

    for result in results:
        if not isinstance(result, dict):
            raise ValueError("slate result entries must be objects")
        stem = str(result.get("artifact_stem", "")).strip()
        if not stem or stem in seen_stems:
            raise ValueError("slate artifact stems must be unique and non-empty")
        seen_stems.add(stem)

        prediction_path = _artifact_path(
            slate_root,
            str(result.get("prediction_path", "")),
            expected_root=slate_root,
        )
        candidate_path = _artifact_path(
            slate_root,
            str(result.get("baseline_candidate_path", "")),
            expected_root=slate_root,
        )
        prediction = _load_json(prediction_path)
        candidate = _load_json(candidate_path)

        prediction_sha = str(prediction.get("record_sha256", "")).strip()
        if prediction_sha != str(result.get("prediction_record_sha256", "")).strip():
            raise ValueError(f"prediction SHA differs from slate manifest: {stem}")
        if (
            candidate.get("record_sha256")
            != result.get("baseline_candidate_record_sha256")
        ):
            raise ValueError(f"baseline candidate SHA differs from slate manifest: {stem}")
        if candidate.get("prediction_record_sha256") != prediction_sha:
            raise ValueError(f"baseline candidate prediction SHA mismatch: {stem}")

        committed_at = datetime.fromisoformat(str(prediction.get("committed_at", "")))
        if committed_at.tzinfo is None:
            raise ValueError(f"prediction commitment is not timezone-aware: {stem}")
        committed_dates.add(committed_at.astimezone(UTC).date().isoformat())

        prediction_output = predictions_root / f"{stem}.json"
        shutil.copyfile(prediction_path, prediction_output)
        candidate_output = candidates_root / f"{stem}.json"
        shutil.copyfile(candidate_path, candidate_output)

        evidence_rows.append(
            {
                "artifact_stem": stem,
                "match_id": str(result.get("match_id", "")),
                "prediction_path": prediction_output.as_posix(),
                "prediction_record_sha256": prediction_sha,
                "baseline_candidate_path": candidate_output.as_posix(),
                "baseline_candidate_record_sha256": candidate["record_sha256"],
            }
        )

    if len(committed_dates) != 1:
        raise ValueError("official slate predictions must share one UTC commitment date")
    slate_date = next(iter(committed_dates))
    slate_id = f"{slate_date}-run-{workflow_run_id}"

    for row in evidence_rows:
        stem = str(row["artifact_stem"])
        baseline_output = baselines_root / f"{stem}.json"
        baseline = finalize_elo_baseline_candidate(
            candidate_path=Path(str(row["baseline_candidate_path"])),
            slate_id=slate_id,
            artifact_id=workflow_artifact_id,
            artifact_sha256=artifact_sha,
            output_path=baseline_output,
        )
        row["baseline_path"] = baseline_output.as_posix()
        row["baseline_record_sha256"] = baseline["record_sha256"]

    output_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(manifest_path, output_root / "slate-manifest.json")
    shutil.copyfile(
        source_reconciliation_path,
        output_root / "source-reconciliation.json",
    )
    shutil.copyfile(
        history_cache_receipt_path,
        output_root / "history-cache-receipt.json",
    )

    receipt: dict[str, Any] = {
        "schema_version": _RECEIPT_SCHEMA,
        "slate_id": slate_id,
        "workflow_run_id": workflow_run_id,
        "workflow_artifact_id": workflow_artifact_id,
        "workflow_artifact_sha256": artifact_sha,
        "workflow_source_sha": source_sha,
        "history_mode": manifest.get("history_mode"),
        "eligible_target_count": eligible,
        "predicted_target_count": predicted,
        "skipped_target_count": skipped,
        "production_eligible": False,
        "scorecard_eligible": True,
    }
    (output_root / "slate-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    summary: dict[str, Any] = {
        "schema_version": _SCHEMA,
        "slate_id": slate_id,
        "production_eligible": False,
        "workflow_run_id": workflow_run_id,
        "workflow_artifact_id": workflow_artifact_id,
        "workflow_artifact_sha256": artifact_sha,
        "workflow_source_sha": source_sha,
        "eligible_target_count": eligible,
        "predicted_target_count": predicted,
        "skipped_target_count": skipped,
        "baseline_count": len(evidence_rows),
        "results": evidence_rows,
    }
    if summary["baseline_count"] != predicted:
        raise RuntimeError("bound baseline count differs from predicted target count")
    (output_root / "bound-evidence-manifest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize a successful Web Shadow slate into artifact-bound evidence"
    )
    parser.add_argument("--slate-root", required=True, type=Path)
    parser.add_argument("--source-reconciliation", required=True, type=Path)
    parser.add_argument("--history-cache-receipt", required=True, type=Path)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--workflow-artifact-id", required=True, type=int)
    parser.add_argument("--workflow-artifact-sha256", required=True)
    parser.add_argument("--workflow-source-sha", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = finalize_web_shadow_slate_evidence(
        slate_root=args.slate_root,
        source_reconciliation_path=args.source_reconciliation,
        history_cache_receipt_path=args.history_cache_receipt,
        workflow_run_id=args.workflow_run_id,
        workflow_artifact_id=args.workflow_artifact_id,
        workflow_artifact_sha256=args.workflow_artifact_sha256,
        workflow_source_sha=args.workflow_source_sha,
        output_root=args.output_root,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
