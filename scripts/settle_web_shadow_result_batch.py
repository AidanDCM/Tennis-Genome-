from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.settle_web_shadow_prediction import settle_from_result_file

_BATCH_SCHEMA = "tennis-genome-web-shadow-result-batch-v1"
_SCORECARD_SCHEMA = "tennis-genome-web-shadow-scorecard-v1"


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


def _safe_result_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"result path must be repository-relative: {value}")
    if len(path.parts) != 3 or path.parts[:2] != ("web-shadow", "results"):
        raise ValueError(f"result path must be under web-shadow/results/: {value}")
    if not path.is_file():
        raise FileNotFoundError(f"result file is missing: {value}")
    return path


def _pending_scorecard_predictions(scorecard_path: Path) -> dict[str, dict[str, Any]]:
    scorecard = _load_json(scorecard_path)
    if scorecard.get("schema_version") != _SCORECARD_SCHEMA:
        raise ValueError("unsupported Web Shadow scorecard schema")
    if scorecard.get("production_eligible") is not False:
        raise ValueError("Web Shadow scorecard must remain non-production")

    pending: dict[str, dict[str, Any]] = {}
    for slate in scorecard.get("slates", []):
        if not isinstance(slate, dict):
            raise ValueError("scorecard slate entries must be objects")
        slate_id = str(slate.get("slate_id", "")).strip()
        for entry in slate.get("predictions", []):
            if not isinstance(entry, dict):
                raise ValueError("scorecard prediction entries must be objects")
            if entry.get("status") != "PENDING":
                continue
            prediction_path = str(entry.get("prediction_path", "")).strip()
            if not prediction_path:
                raise ValueError("pending scorecard prediction lacks prediction_path")
            if prediction_path in pending:
                raise ValueError("pending scorecard prediction paths must be unique")
            pending[prediction_path] = {
                "slate_id": slate_id,
                "match_id": str(entry.get("match_id", "")).strip(),
                "prediction_record_sha256": str(
                    entry.get("prediction_record_sha256", "")
                ).strip(),
            }
    return pending


def settle_web_shadow_result_batch(
    *,
    manifest_path: Path,
    scorecard_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != _BATCH_SCHEMA:
        raise ValueError("unsupported Web Shadow result batch schema")
    result_values = manifest.get("result_paths")
    if not isinstance(result_values, list) or not result_values:
        raise ValueError("result batch must contain a non-empty result_paths list")

    result_paths: list[Path] = []
    seen_result_paths: set[str] = set()
    for value in result_values:
        path = _safe_result_path(str(value))
        key = path.as_posix()
        if key in seen_result_paths:
            raise ValueError(f"duplicate result path in batch: {key}")
        seen_result_paths.add(key)
        result_paths.append(path)

    pending = _pending_scorecard_predictions(scorecard_path)
    if not pending:
        raise RuntimeError("official Web Shadow scorecard has no pending predictions")

    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    seen_prediction_paths: set[str] = set()
    seen_match_ids: set[str] = set()
    correct = 0
    evaluation_eligible = 0

    for result_path in result_paths:
        result = _load_json(result_path)
        prediction_path = str(result.get("prediction_path", "")).strip()
        if prediction_path not in pending:
            raise ValueError(
                "result does not bind a currently pending official scorecard prediction: "
                f"{prediction_path}"
            )
        if prediction_path in seen_prediction_paths:
            raise ValueError(
                f"duplicate prediction settlement in batch: {prediction_path}"
            )
        seen_prediction_paths.add(prediction_path)

        scorecard_entry = pending[prediction_path]
        expected_sha = str(
            result.get("expected_prediction_record_sha256", "")
        ).strip()
        if expected_sha != scorecard_entry["prediction_record_sha256"]:
            raise ValueError(
                "result prediction SHA differs from official scorecard entry"
            )

        match_id = str(result.get("match_id", "")).strip()
        if match_id != scorecard_entry["match_id"]:
            raise ValueError("result match_id differs from official scorecard entry")
        if match_id in seen_match_ids:
            raise ValueError(f"duplicate match_id in result batch: {match_id}")
        seen_match_ids.add(match_id)

        prediction_parts = Path(prediction_path).parts
        if not (
            len(prediction_parts) == 5
            and prediction_parts[0] == "web-shadow"
            and prediction_parts[1] == "slates"
            and prediction_parts[2] == scorecard_entry["slate_id"]
            and prediction_parts[3] == "predictions"
        ):
            raise ValueError(
                "official scorecard prediction path does not match its slate identity"
            )

        stem = Path(prediction_path).stem
        settlement_path = (
            output_root
            / scorecard_entry["slate_id"]
            / "settlements"
            / f"{stem}.json"
        )
        settlement = settle_from_result_file(
            result_path=result_path,
            output_path=settlement_path,
        )
        if settlement.get("match_id") != match_id:
            raise RuntimeError("settlement match_id differs from result batch identity")
        if settlement.get("production_eligible") is not False:
            raise RuntimeError("batch settlement escaped non-production isolation")

        prediction_correct = bool(settlement.get("prediction_correct"))
        evaluation_eligible_result = settlement.get("status") == "COMPLETED"
        if evaluation_eligible_result:
            evaluation_eligible += 1
            if prediction_correct:
                correct += 1
        results.append(
            {
                "slate_id": scorecard_entry["slate_id"],
                "match_id": match_id,
                "result_path": result_path.as_posix(),
                "result_record_sha256": _sha256_file(result_path),
                "prediction_path": prediction_path,
                "prediction_record_sha256": expected_sha,
                "settlement_output_path": settlement_path.as_posix(),
                "settlement_record_sha256": settlement["record_sha256"],
                "winner": settlement["winner"],
                "prediction_correct": prediction_correct,
                "evaluation_eligible": evaluation_eligible_result,
            }
        )

    summary: dict[str, Any] = {
        "schema_version": "tennis-genome-web-shadow-settlement-batch-v1",
        "production_eligible": False,
        "requested_result_count": len(result_paths),
        "settlement_count": len(results),
        "evaluation_eligible_count": evaluation_eligible,
        "excluded_noncompleted_count": len(results) - evaluation_eligible,
        "correct_prediction_count": correct,
        "accuracy": (
            correct / evaluation_eligible if evaluation_eligible else None
        ),
        "slate_count": len({row["slate_id"] for row in results}),
        "results": results,
    }
    if summary["requested_result_count"] != summary["settlement_count"]:
        raise RuntimeError("Web Shadow settlement batch denominator drift")
    (output_root / "settlement-batch-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Settle a batch of pending official Web Shadow predictions"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=Path("web-shadow/scorecard.json"),
    )
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = settle_web_shadow_result_batch(
        manifest_path=args.manifest,
        scorecard_path=args.scorecard,
        output_root=args.output_root,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
