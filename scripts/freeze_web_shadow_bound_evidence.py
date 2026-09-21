from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from scripts.freeze_web_shadow_artifact import (
    _canonical_sha256,
    _load_json,
    _safe_extract,
    _sha256_file,
    _validate_hex_digest,
    _write_json,
)
from scripts.validate_web_shadow_scorecard import validate_web_shadow_scorecard

_BOUND_SCHEMA = "tennis-genome-web-shadow-bound-evidence-v1"
_SCORECARD_SCHEMA = "tennis-genome-web-shadow-scorecard-v1"
_RECEIPT_SCHEMA = "tennis-genome-web-shadow-slate-receipt-v1"


def _bundle_file(root: Path, value: str, *, prefix: str) -> Path:
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"bound evidence path is unsafe: {value}")
    if not rel.parts or rel.parts[0] != prefix:
        raise ValueError(f"bound evidence path has unexpected root: {value}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"bound evidence path escaped artifact root: {value}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"bound evidence file is missing: {value}")
    return resolved


def _verify_record(payload: dict[str, Any], *, label: str) -> str:
    observed = str(payload.get("record_sha256", "")).strip()
    unsigned = dict(payload)
    unsigned.pop("record_sha256", None)
    if _canonical_sha256(unsigned) != observed:
        raise ValueError(f"{label} record digest mismatch")
    return observed


def freeze_web_shadow_bound_evidence(
    *,
    artifact_zip: Path,
    repo_root: Path,
    scorecard_path: Path,
    bound_artifact_id: int,
    bound_artifact_sha256: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    artifact_zip = artifact_zip.resolve()
    if not scorecard_path.is_absolute():
        scorecard_path = repo_root / scorecard_path
    scorecard_path = scorecard_path.resolve()
    try:
        scorecard_path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("scorecard_path must remain inside repo_root") from exc

    if bound_artifact_id <= 0:
        raise ValueError("bound_artifact_id must be positive")
    bound_digest = _validate_hex_digest(
        bound_artifact_sha256,
        label="bound_artifact_sha256",
        length=64,
    )
    if _sha256_file(artifact_zip) != bound_digest:
        raise ValueError("bound artifact ZIP SHA-256 differs from supplied digest")

    original_scorecard_bytes = scorecard_path.read_bytes()
    scorecard = _load_json(scorecard_path)
    if scorecard.get("schema_version") != _SCORECARD_SCHEMA:
        raise ValueError("unsupported Web Shadow scorecard schema")
    if scorecard.get("production_eligible") is not False:
        raise ValueError("Web Shadow scorecard must remain non-production")
    slates = scorecard.get("slates")
    if not isinstance(slates, list):
        raise ValueError("Web Shadow scorecard slates must be a list")

    with tempfile.TemporaryDirectory(prefix="web-shadow-bound-freeze-") as temp_name:
        extracted = Path(temp_name) / "artifact"
        staged = Path(temp_name) / "staged"
        extracted.mkdir(parents=True)
        staged.mkdir(parents=True)
        with zipfile.ZipFile(artifact_zip) as archive:
            _safe_extract(archive, extracted)

        manifest_path = extracted / "bound-evidence-manifest.json"
        receipt_path = extracted / "slate-receipt.json"
        slate_manifest_path = extracted / "slate-manifest.json"
        source_path = extracted / "source-reconciliation.json"
        cache_path = extracted / "history-cache-receipt.json"
        for required in (
            manifest_path,
            receipt_path,
            slate_manifest_path,
            source_path,
            cache_path,
        ):
            if not required.is_file():
                raise FileNotFoundError(f"bound artifact lacks required file: {required.name}")

        manifest = _load_json(manifest_path)
        receipt = _load_json(receipt_path)
        if manifest.get("schema_version") != _BOUND_SCHEMA:
            raise ValueError("unsupported bound evidence schema")
        if manifest.get("production_eligible") is not False:
            raise ValueError("bound evidence escaped non-production isolation")
        if receipt.get("schema_version") != _RECEIPT_SCHEMA:
            raise ValueError("unsupported bound slate receipt schema")
        if receipt.get("scorecard_eligible") is not True:
            raise ValueError("bound slate receipt is not scorecard eligible")
        if receipt.get("production_eligible") is not False:
            raise ValueError("bound slate receipt escaped non-production isolation")

        slate_id = str(manifest.get("slate_id", "")).strip()
        if not slate_id or "/" in slate_id or ".." in slate_id:
            raise ValueError("bound slate_id must be a single safe path segment")
        if receipt.get("slate_id") != slate_id:
            raise ValueError("bound manifest and receipt slate IDs differ")
        if any(
            isinstance(existing, dict) and existing.get("slate_id") == slate_id
            for existing in slates
        ):
            raise ValueError(f"scorecard already contains slate: {slate_id}")

        raw_run_id = int(manifest.get("workflow_run_id", -1))
        raw_artifact_id = int(manifest.get("workflow_artifact_id", -1))
        raw_artifact_sha = _validate_hex_digest(
            str(manifest.get("workflow_artifact_sha256", "")),
            label="workflow_artifact_sha256",
            length=64,
        )
        source_sha = _validate_hex_digest(
            str(manifest.get("workflow_source_sha", "")),
            label="workflow_source_sha",
            length=40,
        )
        for key, expected in (
            ("workflow_run_id", raw_run_id),
            ("workflow_artifact_id", raw_artifact_id),
            ("workflow_artifact_sha256", raw_artifact_sha),
            ("workflow_source_sha", source_sha),
        ):
            if receipt.get(key) != expected:
                raise ValueError(f"bound receipt {key} differs from manifest")

        predicted = int(manifest.get("predicted_target_count", -1))
        skipped = int(manifest.get("skipped_target_count", -1))
        eligible = int(manifest.get("eligible_target_count", -1))
        baseline_count = int(manifest.get("baseline_count", -1))
        results = manifest.get("results")
        if predicted <= 0 or skipped < 0 or eligible <= 0:
            raise ValueError("bound evidence denominator is invalid")
        if predicted + skipped != eligible:
            raise ValueError("bound predicted + skipped differs from eligible denominator")
        if baseline_count != predicted:
            raise ValueError("bound baseline count differs from prediction count")
        if not isinstance(results, list) or len(results) != predicted:
            raise ValueError("bound result count differs from prediction count")
        for key, expected in (
            ("predicted_target_count", predicted),
            ("skipped_target_count", skipped),
            ("eligible_target_count", eligible),
        ):
            if int(receipt.get(key, -1)) != expected:
                raise ValueError(f"bound receipt {key} differs from manifest")

        destination = repo_root / "web-shadow" / "slates" / slate_id
        if destination.exists():
            raise FileExistsError(f"frozen slate directory already exists: {destination}")
        staged_slate = staged / "web-shadow" / "slates" / slate_id
        (staged_slate / "predictions").mkdir(parents=True)
        (staged_slate / "baselines").mkdir(parents=True)
        (staged_slate / "baseline-candidates").mkdir(parents=True)

        scorecard_predictions: list[dict[str, Any]] = []
        seen_stems: set[str] = set()
        seen_matches: set[str] = set()

        for row in results:
            if not isinstance(row, dict):
                raise ValueError("bound evidence result entries must be objects")
            stem = str(row.get("artifact_stem", "")).strip()
            match_id = str(row.get("match_id", "")).strip()
            if not stem or "/" in stem or ".." in stem or stem in seen_stems:
                raise ValueError("bound artifact stems must be unique safe names")
            if not match_id or match_id in seen_matches:
                raise ValueError("bound match IDs must be unique and non-empty")
            seen_stems.add(stem)
            seen_matches.add(match_id)

            prediction_path = _bundle_file(
                extracted, str(row.get("prediction_path", "")), prefix="predictions"
            )
            candidate_path = _bundle_file(
                extracted,
                str(row.get("baseline_candidate_path", "")),
                prefix="baseline-candidates",
            )
            baseline_path = _bundle_file(
                extracted, str(row.get("baseline_path", "")), prefix="baselines"
            )

            prediction = _load_json(prediction_path)
            candidate = _load_json(candidate_path)
            baseline = _load_json(baseline_path)
            prediction_sha = _verify_record(prediction, label="prediction")
            candidate_sha = _verify_record(candidate, label="baseline candidate")
            baseline_sha = _verify_record(baseline, label="baseline")

            if prediction_sha != row.get("prediction_record_sha256"):
                raise ValueError("bound prediction SHA differs from manifest")
            if candidate_sha != row.get("baseline_candidate_record_sha256"):
                raise ValueError("bound candidate SHA differs from manifest")
            if baseline_sha != row.get("baseline_record_sha256"):
                raise ValueError("bound baseline SHA differs from manifest")
            fixture = prediction.get("fixture")
            if not isinstance(fixture, dict) or fixture.get("match_id") != match_id:
                raise ValueError("bound prediction match identity mismatch")
            if prediction.get("model_source_sha") != source_sha:
                raise ValueError("bound prediction model source differs from workflow source")
            if candidate.get("match_id") != match_id:
                raise ValueError("bound candidate match identity mismatch")
            if candidate.get("prediction_record_sha256") != prediction_sha:
                raise ValueError("bound candidate prediction SHA mismatch")
            if baseline.get("match_id") != match_id:
                raise ValueError("bound baseline match identity mismatch")
            if baseline.get("prediction_record_sha256") != prediction_sha:
                raise ValueError("bound baseline prediction SHA mismatch")
            if baseline.get("slate_id") != slate_id:
                raise ValueError("bound baseline slate ID mismatch")
            if int(baseline.get("artifact_id", -1)) != raw_artifact_id:
                raise ValueError("bound baseline raw artifact ID mismatch")
            if baseline.get("artifact_sha256") != raw_artifact_sha:
                raise ValueError("bound baseline raw artifact digest mismatch")
            if baseline.get("production_eligible") is not False:
                raise ValueError("bound baseline escaped non-production isolation")

            selected_player = str(prediction.get("selected_player", ""))
            if selected_player == fixture.get("player_a"):
                selected_probability = float(prediction["p_player_a"])
            elif selected_player == fixture.get("player_b"):
                selected_probability = float(prediction["p_player_b"])
            else:
                raise ValueError("bound selected player is outside fixture")

            shutil.copyfile(
                prediction_path, staged_slate / "predictions" / f"{stem}.json"
            )
            shutil.copyfile(
                candidate_path,
                staged_slate / "baseline-candidates" / f"{stem}.json",
            )
            shutil.copyfile(
                baseline_path, staged_slate / "baselines" / f"{stem}.json"
            )

            scorecard_predictions.append(
                {
                    "match_id": match_id,
                    "prediction_path": (
                        Path("web-shadow/slates") / slate_id / "predictions" / f"{stem}.json"
                    ).as_posix(),
                    "prediction_record_sha256": prediction_sha,
                    "selected_player": selected_player,
                    "selected_probability": selected_probability,
                    "scheduled_start": fixture["scheduled_start"],
                    "status": "PENDING",
                    "baseline_path": (
                        Path("web-shadow/slates") / slate_id / "baselines" / f"{stem}.json"
                    ).as_posix(),
                }
            )

        for source, target in (
            (manifest_path, staged_slate / "bound-evidence-manifest.json"),
            (receipt_path, staged_slate / "slate-receipt.json"),
            (slate_manifest_path, staged_slate / "slate-manifest.json"),
            (source_path, staged_slate / "source-reconciliation.json"),
            (cache_path, staged_slate / "history-cache-receipt.json"),
        ):
            shutil.copyfile(source, target)
        _write_json(
            staged_slate / "bound-artifact-receipt.json",
            {
                "schema_version": "tennis-genome-web-shadow-bound-artifact-receipt-v1",
                "bound_artifact_id": bound_artifact_id,
                "bound_artifact_sha256": bound_digest,
                "raw_workflow_run_id": raw_run_id,
                "raw_artifact_id": raw_artifact_id,
                "raw_artifact_sha256": raw_artifact_sha,
                "production_eligible": False,
            },
        )

        updated = json.loads(json.dumps(scorecard))
        updated["slates"].append(
            {
                "slate_id": slate_id,
                "receipt_path": (
                    Path("web-shadow/slates") / slate_id / "slate-receipt.json"
                ).as_posix(),
                "workflow_run_id": raw_run_id,
                "history_mode": receipt.get("history_mode"),
                "status": "PENDING_SETTLEMENT",
                "predictions": scorecard_predictions,
            }
        )
        updated["official_slate_count"] = len(updated["slates"])
        updated["pending_match_count"] = int(updated.get("pending_match_count", 0)) + predicted
        updated["baseline_match_count"] = int(updated.get("baseline_match_count", 0)) + predicted

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged_slate, destination)
        _write_json(scorecard_path, updated)
        try:
            validate_web_shadow_scorecard(
                scorecard_path=scorecard_path,
                repo_root=repo_root,
            )
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            scorecard_path.write_bytes(original_scorecard_bytes)
            raise

    return {
        "schema_version": "tennis-genome-web-shadow-bound-freeze-summary-v1",
        "slate_id": slate_id,
        "raw_workflow_run_id": raw_run_id,
        "raw_artifact_id": raw_artifact_id,
        "raw_artifact_sha256": raw_artifact_sha,
        "bound_artifact_id": bound_artifact_id,
        "bound_artifact_sha256": bound_digest,
        "predicted_target_count": predicted,
        "skipped_target_count": skipped,
        "official_slate_count": updated["official_slate_count"],
        "pending_match_count": updated["pending_match_count"],
        "settled_match_count": updated.get("settled_match_count", 0),
        "baseline_match_count": updated["baseline_match_count"],
        "production_eligible": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze a bound Web Shadow evidence artifact into the official scorecard"
    )
    parser.add_argument("--artifact-zip", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=Path("web-shadow/scorecard.json"),
    )
    parser.add_argument("--bound-artifact-id", required=True, type=int)
    parser.add_argument("--bound-artifact-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = freeze_web_shadow_bound_evidence(
        artifact_zip=args.artifact_zip,
        repo_root=args.repo_root,
        scorecard_path=args.scorecard,
        bound_artifact_id=args.bound_artifact_id,
        bound_artifact_sha256=args.bound_artifact_sha256,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
