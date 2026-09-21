from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from scripts.derive_web_shadow_elo_baseline import derive_elo_baseline
from scripts.validate_web_shadow_scorecard import validate_web_shadow_scorecard

_SCORECARD_SCHEMA = "tennis-genome-web-shadow-scorecard-v1"
_SLATE_SCHEMA = "tennis-genome-web-shadow-slate-v2"
_SLATE_RECEIPT_SCHEMA = "tennis-genome-web-shadow-slate-receipt-v1"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _validate_hex_digest(value: str, *, label: str, length: int) -> str:
    digest = value.strip().lower()
    if len(digest) != length:
        raise ValueError(f"{label} must contain {length} hexadecimal characters")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be hexadecimal") from exc
    return digest


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"artifact ZIP contains unsafe path: {member.filename}") from exc
    archive.extractall(destination)


def _validate_prediction(
    *,
    prediction: dict[str, Any],
    manifest_result: dict[str, Any],
    local_manifest: dict[str, Any],
    workflow_source_sha: str,
) -> float:
    if prediction.get("record_type") != "WEB_SHADOW_PREDICTION":
        raise ValueError("artifact prediction has unexpected record type")
    if prediction.get("production_eligible") is not False:
        raise ValueError("artifact prediction escaped non-production isolation")

    observed_record_sha = str(prediction.get("record_sha256", "")).strip()
    unsigned = dict(prediction)
    unsigned.pop("record_sha256", None)
    if _canonical_sha256(unsigned) != observed_record_sha:
        raise ValueError("artifact prediction record digest mismatch")
    if observed_record_sha != manifest_result.get("prediction_record_sha256"):
        raise ValueError("artifact prediction SHA differs from slate manifest")

    fixture = prediction.get("fixture")
    if not isinstance(fixture, dict):
        raise ValueError("artifact prediction lacks fixture")
    if fixture.get("match_id") != manifest_result.get("match_id"):
        raise ValueError("artifact prediction match ID differs from slate manifest")
    if fixture.get("scheduled_start") != manifest_result.get("scheduled_start"):
        raise ValueError("artifact prediction start differs from slate manifest")
    if prediction.get("selected_player") != manifest_result.get("selected_player"):
        raise ValueError("artifact prediction selection differs from slate manifest")
    if prediction.get("model_source_sha") != workflow_source_sha:
        raise ValueError("artifact prediction model source differs from workflow source")

    p_a = float(prediction.get("p_player_a"))
    p_b = float(prediction.get("p_player_b"))
    if not (
        math.isfinite(p_a)
        and math.isfinite(p_b)
        and 0.0 < p_a < 1.0
        and 0.0 < p_b < 1.0
        and abs((p_a + p_b) - 1.0) <= 1e-12
    ):
        raise ValueError("artifact prediction probabilities are invalid")
    if abs(p_a - float(manifest_result.get("p_player_a"))) > 1e-12:
        raise ValueError("artifact player A probability differs from slate manifest")
    if abs(p_b - float(manifest_result.get("p_player_b"))) > 1e-12:
        raise ValueError("artifact player B probability differs from slate manifest")

    matchup_sha = str(local_manifest.get("matchup_input_sha256", "")).strip()
    if prediction.get("input_manifest_sha256") != matchup_sha:
        raise ValueError("prediction input SHA differs from local input manifest")

    selected_player = str(prediction["selected_player"])
    if selected_player == fixture.get("player_a"):
        return p_a
    if selected_player == fixture.get("player_b"):
        return p_b
    raise ValueError("artifact selected player is outside fixture")


def freeze_web_shadow_artifact(
    *,
    artifact_zip: Path,
    repo_root: Path,
    scorecard_path: Path,
    slate_id: str,
    workflow_run_id: int,
    artifact_id: int,
    artifact_sha256: str,
    workflow_source_sha: str,
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

    if workflow_run_id <= 0:
        raise ValueError("workflow_run_id must be positive")
    if artifact_id <= 0:
        raise ValueError("artifact_id must be positive")
    artifact_digest = _validate_hex_digest(
        artifact_sha256,
        label="artifact_sha256",
        length=64,
    )
    source_sha = _validate_hex_digest(
        workflow_source_sha,
        label="workflow_source_sha",
        length=40,
    )
    if _sha256_file(artifact_zip) != artifact_digest:
        raise ValueError("artifact ZIP SHA-256 differs from supplied digest")

    slate_name = slate_id.strip()
    if not slate_name or "/" in slate_name or ".." in slate_name:
        raise ValueError("slate_id must be a single safe path segment")

    original_scorecard_bytes = scorecard_path.read_bytes()
    scorecard = _load_json(scorecard_path)
    if scorecard.get("schema_version") != _SCORECARD_SCHEMA:
        raise ValueError("unsupported Web Shadow scorecard schema")
    if scorecard.get("production_eligible") is not False:
        raise ValueError("Web Shadow scorecard must remain non-production")
    slates = scorecard.get("slates")
    if not isinstance(slates, list):
        raise ValueError("Web Shadow scorecard slates must be a list")
    if any(
        isinstance(existing, dict) and existing.get("slate_id") == slate_name
        for existing in slates
    ):
        raise ValueError(f"scorecard already contains slate: {slate_name}")

    destination = repo_root / "web-shadow" / "slates" / slate_name
    if destination.exists():
        raise FileExistsError(f"frozen slate directory already exists: {destination}")

    with tempfile.TemporaryDirectory(prefix="web-shadow-freeze-") as temp_name:
        extracted = Path(temp_name) / "artifact"
        staged = Path(temp_name) / "staged"
        extracted.mkdir(parents=True)
        staged.mkdir(parents=True)
        with zipfile.ZipFile(artifact_zip) as archive:
            _safe_extract(archive, extracted)

        artifact_run_root = extracted / "web-shadow-slate-run"
        slate_manifest_path = artifact_run_root / "slate-manifest.json"
        source_reconciliation_path = (
            extracted / "data/wta-live-base/2026-source-reconciliation.json"
        )
        history_cache_receipt_path = (
            extracted / "data/wta-live-base/history-cache-receipt.json"
        )
        for required in (
            slate_manifest_path,
            source_reconciliation_path,
            history_cache_receipt_path,
        ):
            if not required.is_file():
                raise FileNotFoundError(f"artifact lacks required file: {required}")

        slate_manifest = _load_json(slate_manifest_path)
        if slate_manifest.get("schema_version") != _SLATE_SCHEMA:
            raise ValueError("unsupported Web Shadow slate artifact schema")
        if slate_manifest.get("production_eligible") is not False:
            raise ValueError("Web Shadow slate artifact must remain non-production")

        results = slate_manifest.get("results")
        if not isinstance(results, list) or not results:
            raise ValueError("Web Shadow slate artifact has no predictions")
        predicted = int(slate_manifest.get("predicted_target_count", -1))
        skipped = int(slate_manifest.get("skipped_target_count", -1))
        eligible = int(slate_manifest.get("eligible_target_count", -1))
        if predicted != len(results):
            raise ValueError("slate predicted count differs from result records")
        if predicted + skipped != eligible:
            raise ValueError("slate predicted + skipped differs from eligible denominator")

        staged_slate = staged / "web-shadow" / "slates" / slate_name
        (staged_slate / "predictions").mkdir(parents=True)
        (staged_slate / "baselines").mkdir(parents=True)

        scorecard_predictions: list[dict[str, Any]] = []
        seen_match_ids: set[str] = set()
        seen_stems: set[str] = set()
        for result in results:
            if not isinstance(result, dict):
                raise ValueError("slate result entries must be objects")
            stem = str(result.get("artifact_stem", "")).strip()
            match_id = str(result.get("match_id", "")).strip()
            if not stem or "/" in stem or ".." in stem or stem in seen_stems:
                raise ValueError("slate artifact stems must be unique safe names")
            if not match_id or match_id in seen_match_ids:
                raise ValueError("slate match IDs must be unique and non-empty")
            seen_stems.add(stem)
            seen_match_ids.add(match_id)

            match_root = artifact_run_root / "matches" / stem
            prediction_path = match_root / "prediction.json"
            matchup_input_path = match_root / "matchup-input.json"
            local_manifest_path = match_root / "local-input-manifest.json"
            for required in (
                prediction_path,
                matchup_input_path,
                local_manifest_path,
            ):
                if not required.is_file():
                    raise FileNotFoundError(
                        f"artifact match {stem} lacks required file: {required.name}"
                    )

            expected_prediction_path = (
                Path("web-shadow-slate-run")
                / "matches"
                / stem
                / "prediction.json"
            ).as_posix()
            if result.get("prediction_path") != expected_prediction_path:
                raise ValueError("slate prediction path does not match artifact stem")

            prediction = _load_json(prediction_path)
            local_manifest = _load_json(local_manifest_path)
            selected_probability = _validate_prediction(
                prediction=prediction,
                manifest_result=result,
                local_manifest=local_manifest,
                workflow_source_sha=source_sha,
            )
            if _sha256_file(matchup_input_path) != local_manifest.get(
                "matchup_input_sha256"
            ):
                raise ValueError("artifact matchup input SHA differs from local manifest")

            frozen_prediction = staged_slate / "predictions" / f"{stem}.json"
            shutil.copyfile(prediction_path, frozen_prediction)

            frozen_baseline = staged_slate / "baselines" / f"{stem}.json"
            baseline = derive_elo_baseline(
                matchup_input_path=matchup_input_path,
                local_input_manifest_path=local_manifest_path,
                prediction_path=prediction_path,
                slate_id=slate_name,
                artifact_id=artifact_id,
                artifact_sha256=artifact_digest,
                output_path=frozen_baseline,
            )
            if baseline.get("match_id") != match_id:
                raise RuntimeError("derived baseline match identity drift")
            if baseline.get("prediction_record_sha256") != prediction.get(
                "record_sha256"
            ):
                raise RuntimeError("derived baseline prediction SHA drift")

            scorecard_predictions.append(
                {
                    "match_id": match_id,
                    "prediction_path": (
                        Path("web-shadow/slates")
                        / slate_name
                        / "predictions"
                        / f"{stem}.json"
                    ).as_posix(),
                    "prediction_record_sha256": prediction["record_sha256"],
                    "selected_player": prediction["selected_player"],
                    "selected_probability": selected_probability,
                    "scheduled_start": prediction["fixture"]["scheduled_start"],
                    "status": "PENDING",
                    "baseline_path": (
                        Path("web-shadow/slates")
                        / slate_name
                        / "baselines"
                        / f"{stem}.json"
                    ).as_posix(),
                }
            )

        shutil.copyfile(
            slate_manifest_path,
            staged_slate / "slate-manifest.json",
        )
        shutil.copyfile(
            source_reconciliation_path,
            staged_slate / "source-reconciliation.json",
        )
        shutil.copyfile(
            history_cache_receipt_path,
            staged_slate / "history-cache-receipt.json",
        )

        receipt = {
            "schema_version": _SLATE_RECEIPT_SCHEMA,
            "slate_id": slate_name,
            "workflow_run_id": workflow_run_id,
            "workflow_artifact_id": artifact_id,
            "workflow_artifact_sha256": artifact_digest,
            "workflow_source_sha": source_sha,
            "history_mode": slate_manifest["history_mode"],
            "eligible_target_count": eligible,
            "predicted_target_count": predicted,
            "skipped_target_count": skipped,
            "production_eligible": False,
            "scorecard_eligible": True,
        }
        _write_json(staged_slate / "slate-receipt.json", receipt)

        updated = json.loads(json.dumps(scorecard))
        updated_slates = updated["slates"]
        updated_slates.append(
            {
                "slate_id": slate_name,
                "receipt_path": (
                    Path("web-shadow/slates") / slate_name / "slate-receipt.json"
                ).as_posix(),
                "workflow_run_id": workflow_run_id,
                "history_mode": slate_manifest["history_mode"],
                "status": "PENDING_SETTLEMENT",
                "predictions": scorecard_predictions,
            }
        )
        updated["official_slate_count"] = len(updated_slates)
        updated["pending_match_count"] = int(updated.get("pending_match_count", 0)) + predicted
        updated["baseline_match_count"] = int(updated.get("baseline_match_count", 0)) + predicted
        if int(updated.get("settled_match_count", 0)) < 0:
            raise ValueError("scorecard settled_match_count is invalid")

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
        "schema_version": "tennis-genome-web-shadow-freeze-summary-v1",
        "slate_id": slate_name,
        "workflow_run_id": workflow_run_id,
        "artifact_id": artifact_id,
        "artifact_sha256": artifact_digest,
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
        description="Freeze a successful Web Shadow Actions artifact into the official scorecard"
    )
    parser.add_argument("--artifact-zip", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=Path("web-shadow/scorecard.json"),
    )
    parser.add_argument("--slate-id", required=True)
    parser.add_argument("--workflow-run-id", required=True, type=int)
    parser.add_argument("--artifact-id", required=True, type=int)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--workflow-source-sha", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = freeze_web_shadow_artifact(
        artifact_zip=args.artifact_zip,
        repo_root=args.repo_root,
        scorecard_path=args.scorecard,
        slate_id=args.slate_id,
        workflow_run_id=args.workflow_run_id,
        artifact_id=args.artifact_id,
        artifact_sha256=args.artifact_sha256,
        workflow_source_sha=args.workflow_source_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
