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
    _safe_extract,
    _sha256_file,
    _validate_hex_digest,
    _write_json,
)
from scripts.validate_web_shadow_scorecard import (
    _compute_baseline_comparison,
    _compute_metrics,
    validate_web_shadow_scorecard,
)

_BATCH_SCHEMA = "tennis-genome-web-shadow-settlement-batch-v1"
_MANIFEST_SCHEMA = "tennis-genome-web-shadow-result-batch-v1"
_SCORECARD_SCHEMA = "tennis-genome-web-shadow-scorecard-v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return payload


def _repo_file(root: Path, value: str, *, prefix: tuple[str, ...]) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"path must be repository-relative: {value}")
    if relative.parts[: len(prefix)] != prefix:
        raise ValueError(f"path has unexpected repository root: {value}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escaped repository root: {value}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"referenced repository file is missing: {value}")
    return resolved


def _artifact_file(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"settlement artifact path is unsafe: {value}")
    if not relative.parts or relative.parts[0] != "web-shadow-settlement-batch":
        raise ValueError(f"settlement artifact path has unexpected root: {value}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"settlement artifact path escaped artifact root: {value}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"settlement artifact file is missing: {value}")
    return resolved


def _assert_record_digest(record: dict[str, Any], *, label: str) -> str:
    observed = str(record.get("record_sha256", "")).strip().lower()
    unsigned = dict(record)
    unsigned.pop("record_sha256", None)
    if not observed or _canonical_sha256(unsigned) != observed:
        raise ValueError(f"{label} record digest mismatch")
    return observed


def _pending_entries(
    scorecard: dict[str, Any],
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    pending: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for slate in scorecard.get("slates", []):
        if not isinstance(slate, dict):
            raise ValueError("scorecard slate entries must be objects")
        slate_id = str(slate.get("slate_id", "")).strip()
        predictions = slate.get("predictions")
        if not slate_id or not isinstance(predictions, list):
            raise ValueError("scorecard slate identity/predictions are invalid")
        for entry in predictions:
            if not isinstance(entry, dict) or entry.get("status") != "PENDING":
                continue
            prediction_path = str(entry.get("prediction_path", "")).strip()
            if not prediction_path:
                raise ValueError("pending scorecard entry lacks prediction_path")
            if prediction_path in pending:
                raise ValueError("pending scorecard prediction paths must be unique")
            pending[prediction_path] = (slate, entry)
    return pending


def _refresh_scorecard_derived_fields(
    *,
    scorecard: dict[str, Any],
    repo_root: Path,
) -> None:
    pending_count = 0
    settled_count = 0
    baseline_count = 0
    metric_rows: list[dict[str, float | bool]] = []
    baseline_genome_rows: list[dict[str, float | bool]] = []
    baseline_rows: list[dict[str, float | bool]] = []

    slates = scorecard.get("slates")
    if not isinstance(slates, list):
        raise ValueError("scorecard slates must be a list")

    for slate in slates:
        if not isinstance(slate, dict):
            raise ValueError("scorecard slate entries must be objects")
        predictions = slate.get("predictions")
        if not isinstance(predictions, list) or not predictions:
            raise ValueError("official slate must contain predictions")
        slate_settled = 0

        for entry in predictions:
            if not isinstance(entry, dict):
                raise ValueError("scorecard prediction entries must be objects")
            status = str(entry.get("status", "")).strip()
            baseline_path_raw = str(entry.get("baseline_path", "")).strip()
            if baseline_path_raw:
                baseline_count += 1

            if status == "PENDING":
                pending_count += 1
                continue
            if status != "SETTLED":
                raise ValueError(f"unsupported scorecard prediction status: {status}")

            settled_count += 1
            slate_settled += 1
            prediction_path = _repo_file(
                repo_root,
                str(entry.get("prediction_path", "")),
                prefix=("web-shadow", "slates"),
            )
            settlement_path = _repo_file(
                repo_root,
                str(entry.get("settlement_path", "")),
                prefix=("web-shadow", "slates"),
            )
            prediction = _load_json(prediction_path)
            settlement = _load_json(settlement_path)
            if str(settlement.get("status", "")).strip().upper() != "COMPLETED":
                continue

            fixture = prediction.get("fixture")
            if not isinstance(fixture, dict):
                raise ValueError("settled prediction fixture is missing")
            winner = str(settlement.get("winner", ""))
            player_a = str(fixture.get("player_a", ""))
            player_b = str(fixture.get("player_b", ""))
            selected_player = str(prediction.get("selected_player", ""))
            selected_probability = (
                float(prediction["p_player_a"])
                if selected_player == player_a
                else float(prediction["p_player_b"])
            )
            genome_row = {
                "p_player_a": float(prediction["p_player_a"]),
                "p_player_b": float(prediction["p_player_b"]),
                "selected_probability": selected_probability,
                "actual_player_a_won": winner == player_a,
                "prediction_correct": winner == selected_player,
            }
            metric_rows.append(genome_row)

            if baseline_path_raw:
                baseline = _load_json(
                    _repo_file(
                        repo_root,
                        baseline_path_raw,
                        prefix=("web-shadow", "slates"),
                    )
                )
                baseline_p_a = float(baseline["p_player_a"])
                baseline_p_b = float(baseline["p_player_b"])
                baseline_genome_rows.append(genome_row)
                baseline_rows.append(
                    {
                        "p_player_a": baseline_p_a,
                        "p_player_b": baseline_p_b,
                        "selected_probability": max(baseline_p_a, baseline_p_b),
                        "actual_player_a_won": winner == player_a,
                        "prediction_correct": (
                            winner == str(baseline.get("selected_player", ""))
                        ),
                    }
                )

        slate["status"] = (
            "SETTLED"
            if slate_settled == len(predictions)
            else "PENDING_SETTLEMENT"
        )

    scorecard["official_slate_count"] = len(slates)
    scorecard["pending_match_count"] = pending_count
    scorecard["settled_match_count"] = settled_count
    scorecard["baseline_match_count"] = baseline_count

    if metric_rows:
        scorecard["metrics"] = _compute_metrics(metric_rows)
    else:
        scorecard.pop("metrics", None)

    if baseline_rows:
        scorecard["baseline_comparison"] = _compute_baseline_comparison(
            genome_rows=baseline_genome_rows,
            baseline_rows=baseline_rows,
        )
    else:
        scorecard.pop("baseline_comparison", None)


def apply_web_shadow_settlement_batch(
    *,
    artifact_zip: Path,
    repo_root: Path,
    scorecard_path: Path,
    source_workflow_run_id: int,
    source_workflow_sha: str,
    settlement_artifact_id: int,
    settlement_artifact_sha256: str,
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

    if source_workflow_run_id <= 0 or settlement_artifact_id <= 0:
        raise ValueError("workflow/artifact IDs must be positive")
    source_sha = _validate_hex_digest(
        source_workflow_sha,
        label="source_workflow_sha",
        length=40,
    )
    artifact_digest = _validate_hex_digest(
        settlement_artifact_sha256,
        label="settlement_artifact_sha256",
        length=64,
    )
    if _sha256_file(artifact_zip) != artifact_digest:
        raise ValueError("settlement artifact ZIP SHA-256 differs from supplied digest")

    original_scorecard_bytes = scorecard_path.read_bytes()
    scorecard = _load_json(scorecard_path)
    if scorecard.get("schema_version") != _SCORECARD_SCHEMA:
        raise ValueError("unsupported Web Shadow scorecard schema")
    if scorecard.get("production_eligible") is not False:
        raise ValueError("Web Shadow scorecard must remain non-production")
    pending = _pending_entries(scorecard)
    if not pending:
        raise RuntimeError("official Web Shadow scorecard has no pending predictions")

    copied_paths: list[Path] = []
    created_dirs: set[Path] = set()

    with tempfile.TemporaryDirectory(prefix="web-shadow-settlement-apply-") as temp_name:
        extracted = Path(temp_name) / "artifact"
        extracted.mkdir(parents=True)
        with zipfile.ZipFile(artifact_zip) as archive:
            _safe_extract(archive, extracted)

        batch_root = extracted / "web-shadow-settlement-batch"
        summary_path = batch_root / "settlement-batch-summary.json"
        manifest_path = batch_root / "result-batch-manifest.json"
        for required in (summary_path, manifest_path):
            if not required.is_file():
                raise FileNotFoundError(
                    f"settlement artifact lacks required file: {required.name}"
                )

        summary = _load_json(summary_path)
        manifest = _load_json(manifest_path)
        if summary.get("schema_version") != _BATCH_SCHEMA:
            raise ValueError("unsupported settlement batch artifact schema")
        if summary.get("production_eligible") is not False:
            raise ValueError("settlement batch artifact escaped non-production isolation")
        if manifest.get("schema_version") != _MANIFEST_SCHEMA:
            raise ValueError("unsupported settlement result manifest schema")

        requested = int(summary.get("requested_result_count", -1))
        settlement_count = int(summary.get("settlement_count", -1))
        eligible_count = int(summary.get("evaluation_eligible_count", -1))
        excluded_count = int(summary.get("excluded_noncompleted_count", -1))
        rows = summary.get("results")
        result_paths = manifest.get("result_paths")
        if requested <= 0 or settlement_count != requested:
            raise ValueError("settlement batch denominator is invalid")
        if eligible_count < 0 or excluded_count < 0:
            raise ValueError("settlement evaluation denominator is invalid")
        if eligible_count + excluded_count != settlement_count:
            raise ValueError("settlement evaluation denominator drift")
        if not isinstance(rows, list) or len(rows) != settlement_count:
            raise ValueError("settlement batch result count differs from denominator")
        if not isinstance(result_paths, list) or len(result_paths) != requested:
            raise ValueError("settlement result manifest count differs from denominator")
        if [str(row.get("result_path", "")) for row in rows] != [
            str(value) for value in result_paths
        ]:
            raise ValueError("settlement artifact rows differ from result manifest order")

        seen_predictions: set[str] = set()
        seen_matches: set[str] = set()
        updates: list[tuple[dict[str, Any], Path, Path]] = []

        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("settlement batch rows must be objects")
            prediction_path_raw = str(row.get("prediction_path", "")).strip()
            result_path_raw = str(row.get("result_path", "")).strip()
            slate_id = str(row.get("slate_id", "")).strip()
            match_id = str(row.get("match_id", "")).strip()
            if prediction_path_raw in seen_predictions:
                raise ValueError("settlement batch repeats a prediction")
            if not match_id or match_id in seen_matches:
                raise ValueError("settlement batch match IDs must be unique and non-empty")
            seen_predictions.add(prediction_path_raw)
            seen_matches.add(match_id)

            pending_pair = pending.get(prediction_path_raw)
            if pending_pair is None:
                raise ValueError(
                    "settlement artifact does not bind a currently pending official prediction"
                )
            slate, entry = pending_pair
            if slate.get("slate_id") != slate_id:
                raise ValueError("settlement artifact slate identity mismatch")
            if entry.get("match_id") != match_id:
                raise ValueError("settlement artifact match identity mismatch")
            prediction_sha = str(entry.get("prediction_record_sha256", "")).strip()
            if row.get("prediction_record_sha256") != prediction_sha:
                raise ValueError("settlement artifact prediction SHA mismatch")

            result_path = _repo_file(
                repo_root,
                result_path_raw,
                prefix=("web-shadow", "results"),
            )
            result_sha = _validate_hex_digest(
                str(row.get("result_record_sha256", "")),
                label="result_record_sha256",
                length=64,
            )
            if _sha256_file(result_path) != result_sha:
                raise ValueError("committed result file SHA differs from settlement artifact")
            result = _load_json(result_path)
            if result.get("production_eligible") is not False:
                raise ValueError("settlement result escaped non-production isolation")
            if not str(result.get("score", "")).strip():
                raise ValueError("settlement result evidence lacks score")
            if result.get("match_id") != match_id:
                raise ValueError("settlement result match identity mismatch")
            if result.get("prediction_path") != prediction_path_raw:
                raise ValueError("settlement result prediction path mismatch")
            if result.get("expected_prediction_record_sha256") != prediction_sha:
                raise ValueError("settlement result prediction SHA mismatch")

            stem = Path(prediction_path_raw).stem
            expected_artifact_path = (
                Path("web-shadow-settlement-batch")
                / slate_id
                / "settlements"
                / f"{stem}.json"
            ).as_posix()
            if row.get("settlement_output_path") != expected_artifact_path:
                raise ValueError("settlement output path differs from immutable slate identity")
            settlement_source = _artifact_file(extracted, expected_artifact_path)
            settlement = _load_json(settlement_source)
            settlement_sha = _assert_record_digest(
                settlement,
                label=f"settlement {match_id}",
            )
            if settlement_sha != row.get("settlement_record_sha256"):
                raise ValueError("settlement record SHA differs from batch artifact")
            if settlement.get("production_eligible") is not False:
                raise ValueError("settlement escaped non-production isolation")
            if settlement.get("match_id") != match_id:
                raise ValueError("settlement record match identity mismatch")
            if settlement.get("prediction_record_sha256") != prediction_sha:
                raise ValueError("settlement record prediction SHA mismatch")
            if settlement.get("result_record_path") != result_path_raw:
                raise ValueError("settlement record result path mismatch")
            if bool(settlement.get("prediction_correct")) != bool(
                row.get("prediction_correct")
            ):
                raise ValueError("settlement correctness differs from batch artifact")
            if bool(row.get("evaluation_eligible")) != (
                str(settlement.get("status", "")).strip().upper() == "COMPLETED"
            ):
                raise ValueError("settlement evaluation eligibility mismatch")
            for field in (
                "winner",
                "status",
                "result_source_url",
                "result_observed_at",
            ):
                if settlement.get(field) != result.get(field):
                    raise ValueError(f"settlement/result evidence mismatch for {field}")

            destination = (
                repo_root
                / "web-shadow"
                / "slates"
                / slate_id
                / "settlements"
                / f"{stem}.json"
            )
            if destination.exists():
                raise FileExistsError(
                    f"official settlement already exists: {destination}"
                )
            updates.append((entry, settlement_source, destination))

        try:
            for entry, source, destination in updates:
                if not destination.parent.exists():
                    destination.parent.mkdir(parents=True)
                    created_dirs.add(destination.parent)
                shutil.copyfile(source, destination)
                copied_paths.append(destination)
                settlement = _load_json(destination)
                entry["status"] = "SETTLED"
                entry["settlement_path"] = destination.relative_to(repo_root).as_posix()
                entry["settlement_record_sha256"] = settlement["record_sha256"]
                result_path = str(settlement["result_record_path"])
                entry["result_record_sha256"] = _sha256_file(repo_root / result_path)

            _refresh_scorecard_derived_fields(
                scorecard=scorecard,
                repo_root=repo_root,
            )
            _write_json(scorecard_path, scorecard)
            validation = validate_web_shadow_scorecard(
                scorecard_path=scorecard_path,
                repo_root=repo_root,
            )
        except Exception:
            for path in reversed(copied_paths):
                path.unlink(missing_ok=True)
            for directory in sorted(created_dirs, key=lambda value: len(value.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            scorecard_path.write_bytes(original_scorecard_bytes)
            raise

    return {
        "schema_version": "tennis-genome-web-shadow-settlement-apply-summary-v1",
        "source_workflow_run_id": source_workflow_run_id,
        "source_workflow_sha": source_sha,
        "settlement_artifact_id": settlement_artifact_id,
        "settlement_artifact_sha256": artifact_digest,
        "applied_settlement_count": settlement_count,
        "evaluation_eligible_count": eligible_count,
        "excluded_noncompleted_count": excluded_count,
        "affected_slate_ids": sorted({str(row["slate_id"]) for row in rows}),
        "official_slate_count": validation["official_slate_count"],
        "pending_match_count": validation["pending_match_count"],
        "settled_match_count": validation["settled_match_count"],
        "production_eligible": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply a retained Web Shadow settlement batch to the official scorecard"
    )
    parser.add_argument("--artifact-zip", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=Path("web-shadow/scorecard.json"),
    )
    parser.add_argument("--source-workflow-run-id", required=True, type=int)
    parser.add_argument("--source-workflow-sha", required=True)
    parser.add_argument("--settlement-artifact-id", required=True, type=int)
    parser.add_argument("--settlement-artifact-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = apply_web_shadow_settlement_batch(
        artifact_zip=args.artifact_zip,
        repo_root=args.repo_root,
        scorecard_path=args.scorecard,
        source_workflow_run_id=args.source_workflow_run_id,
        source_workflow_sha=args.source_workflow_sha,
        settlement_artifact_id=args.settlement_artifact_id,
        settlement_artifact_sha256=args.settlement_artifact_sha256,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
