from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

_SCORECARD_SCHEMA = "tennis-genome-web-shadow-scorecard-v1"
_METRICS_SCHEMA = "tennis-genome-web-shadow-metrics-v1"
_BASELINE_SCHEMA = "tennis-genome-web-shadow-baseline-v1"
_BASELINE_COMPARISON_SCHEMA = "tennis-genome-web-shadow-baseline-comparison-v1"
_BASELINE_NAME = "overall_elo_v1"
_ALLOWED_STATUSES = {"PENDING", "SETTLED"}


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


def _repo_path(root: Path, value: str, *, prefix: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"path must be repository-relative: {value}")
    if not relative.parts or relative.parts[0] != prefix:
        raise ValueError(f"path must remain under {prefix}/: {value}")
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"referenced scorecard file is missing: {value}")
    return path


def _assert_record_digest(record: dict[str, Any], *, label: str) -> str:
    observed = str(record.get("record_sha256", "")).strip()
    unsigned = dict(record)
    unsigned.pop("record_sha256", None)
    if not observed or _canonical_sha256(unsigned) != observed:
        raise ValueError(f"{label} record digest mismatch")
    return observed


def _compute_metrics(rows: list[dict[str, float | bool]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot compute Web Shadow metrics without settlements")

    correct = sum(bool(row["prediction_correct"]) for row in rows)
    accuracy = correct / len(rows)
    brier = sum(
        (float(row["p_player_a"]) - float(row["actual_player_a_won"])) ** 2
        for row in rows
    ) / len(rows)
    log_loss = sum(
        -math.log(
            float(row["p_player_a"])
            if bool(row["actual_player_a_won"])
            else float(row["p_player_b"])
        )
        for row in rows
    ) / len(rows)
    mean_selected_probability = sum(
        float(row["selected_probability"]) for row in rows
    ) / len(rows)

    buckets: list[dict[str, Any]] = []
    for lower_int in range(50, 100, 10):
        lower = lower_int / 100.0
        upper = (lower_int + 10) / 100.0
        members = [
            row
            for row in rows
            if lower <= float(row["selected_probability"]) < upper
        ]
        if not members:
            continue
        bucket_correct = sum(bool(row["prediction_correct"]) for row in members)
        buckets.append(
            {
                "label": f"{lower:.2f}-{upper:.2f}",
                "lower_bound": lower,
                "upper_bound": upper,
                "match_count": len(members),
                "correct_prediction_count": bucket_correct,
                "accuracy": bucket_correct / len(members),
                "mean_selected_probability": sum(
                    float(row["selected_probability"]) for row in members
                )
                / len(members),
            }
        )

    return {
        "schema_version": _METRICS_SCHEMA,
        "settled_match_count": len(rows),
        "correct_prediction_count": correct,
        "accuracy": accuracy,
        "brier_score": brier,
        "log_loss": log_loss,
        "mean_selected_probability": mean_selected_probability,
        "calibration_gap_accuracy_minus_mean_selected_probability": (
            accuracy - mean_selected_probability
        ),
        "confidence_buckets": buckets,
    }


def _compute_baseline_comparison(
    *,
    genome_rows: list[dict[str, float | bool]],
    baseline_rows: list[dict[str, float | bool]],
) -> dict[str, Any]:
    if len(genome_rows) != len(baseline_rows):
        raise ValueError("Genome and baseline comparison denominators differ")
    if not genome_rows:
        raise ValueError("baseline comparison requires at least one settled match")

    genome_metrics = _compute_metrics(genome_rows)
    baseline_metrics = _compute_metrics(baseline_rows)
    return {
        "schema_version": _BASELINE_COMPARISON_SCHEMA,
        "baseline_name": _BASELINE_NAME,
        "settled_match_count": len(genome_rows),
        "genome": genome_metrics,
        "baseline": baseline_metrics,
        "brier_improvement_baseline_minus_genome": (
            float(baseline_metrics["brier_score"])
            - float(genome_metrics["brier_score"])
        ),
        "log_loss_improvement_baseline_minus_genome": (
            float(baseline_metrics["log_loss"])
            - float(genome_metrics["log_loss"])
        ),
    }


def _assert_metric_payload(expected: Any, observed: Any, *, path: str) -> None:
    if isinstance(expected, float):
        try:
            value = float(observed)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"scorecard metric is not numeric: {path}") from exc
        if not math.isfinite(value) or abs(expected - value) > 1e-12:
            raise ValueError(f"scorecard metric mismatch: {path}")
        return
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(observed) != set(expected):
            raise ValueError(f"scorecard metric object mismatch: {path}")
        for key, value in expected.items():
            _assert_metric_payload(value, observed[key], path=f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(observed) != len(expected):
            raise ValueError(f"scorecard metric array mismatch: {path}")
        for index, value in enumerate(expected):
            _assert_metric_payload(value, observed[index], path=f"{path}[{index}]")
        return
    if observed != expected:
        raise ValueError(f"scorecard metric mismatch: {path}")


def validate_web_shadow_scorecard(
    *,
    scorecard_path: Path,
    repo_root: Path = Path("."),
) -> dict[str, int]:
    scorecard = _load_json(scorecard_path)
    if scorecard.get("schema_version") != _SCORECARD_SCHEMA:
        raise ValueError("unsupported Web Shadow scorecard schema")
    if scorecard.get("production_eligible") is not False:
        raise ValueError("Web Shadow scorecard must remain non-production")

    slates = scorecard.get("slates")
    if not isinstance(slates, list) or not slates:
        raise ValueError("Web Shadow scorecard must contain at least one official slate")

    seen_slate_ids: set[str] = set()
    seen_match_ids: set[str] = set()
    pending = 0
    settled = 0
    metric_rows: list[dict[str, float | bool]] = []
    baseline_genome_metric_rows: list[dict[str, float | bool]] = []
    baseline_metric_rows: list[dict[str, float | bool]] = []
    baseline_count = 0

    for slate in slates:
        if not isinstance(slate, dict):
            raise ValueError("scorecard slate entries must be objects")
        slate_id = str(slate.get("slate_id", "")).strip()
        if not slate_id or slate_id in seen_slate_ids:
            raise ValueError("scorecard slate IDs must be unique and non-empty")
        seen_slate_ids.add(slate_id)

        receipt_path = _repo_path(
            repo_root,
            str(slate.get("receipt_path", "")),
            prefix="web-shadow",
        )
        receipt = _load_json(receipt_path)
        if receipt.get("scorecard_eligible") is not True:
            raise ValueError(f"slate receipt is not scorecard-eligible: {slate_id}")
        if receipt.get("production_eligible") is not False:
            raise ValueError(f"slate receipt escaped non-production isolation: {slate_id}")
        if receipt.get("slate_id") != slate_id:
            raise ValueError(f"slate receipt ID mismatch: {slate_id}")
        if int(receipt.get("workflow_run_id", -1)) != int(
            slate.get("workflow_run_id", -2)
        ):
            raise ValueError(f"slate workflow run mismatch: {slate_id}")
        if receipt.get("history_mode") != slate.get("history_mode"):
            raise ValueError(f"slate history mode mismatch: {slate_id}")

        predictions = slate.get("predictions")
        if not isinstance(predictions, list) or not predictions:
            raise ValueError(f"official slate has no predictions: {slate_id}")
        if len(predictions) != int(receipt.get("predicted_target_count", -1)):
            raise ValueError(f"slate prediction count differs from receipt: {slate_id}")

        slate_root = receipt_path.parent
        expected_prediction_root = slate_root / "predictions"
        slate_settled = 0

        for entry in predictions:
            if not isinstance(entry, dict):
                raise ValueError("scorecard prediction entries must be objects")
            status = str(entry.get("status", "")).strip()
            if status not in _ALLOWED_STATUSES:
                raise ValueError(f"unsupported official scorecard status: {status}")

            match_id = str(entry.get("match_id", "")).strip()
            if not match_id or match_id in seen_match_ids:
                raise ValueError("official scorecard match IDs must be unique")
            seen_match_ids.add(match_id)

            prediction_path = _repo_path(
                repo_root,
                str(entry.get("prediction_path", "")),
                prefix="web-shadow",
            )
            try:
                prediction_path.relative_to(expected_prediction_root)
            except ValueError as exc:
                raise ValueError(
                    f"prediction is outside its immutable slate directory: {match_id}"
                ) from exc

            prediction = _load_json(prediction_path)
            if prediction.get("production_eligible") is not False:
                raise ValueError(f"prediction escaped non-production isolation: {match_id}")
            if prediction.get("record_type") != "WEB_SHADOW_PREDICTION":
                raise ValueError(f"unexpected prediction record type: {match_id}")

            observed_sha = _assert_record_digest(
                prediction,
                label=f"prediction {match_id}",
            )
            if observed_sha != str(entry.get("prediction_record_sha256", "")):
                raise ValueError(f"scorecard prediction SHA mismatch: {match_id}")

            fixture = prediction.get("fixture")
            if not isinstance(fixture, dict):
                raise ValueError(f"prediction fixture is missing: {match_id}")
            if fixture.get("match_id") != match_id:
                raise ValueError(f"scorecard match identity mismatch: {match_id}")
            if fixture.get("scheduled_start") != entry.get("scheduled_start"):
                raise ValueError(f"scorecard scheduled start mismatch: {match_id}")

            committed_at = datetime.fromisoformat(str(prediction["committed_at"]))
            scheduled_start = datetime.fromisoformat(str(fixture["scheduled_start"]))
            if committed_at.tzinfo is None or scheduled_start.tzinfo is None:
                raise ValueError(f"scorecard chronology must be timezone-aware: {match_id}")
            if committed_at >= scheduled_start:
                raise ValueError(f"prediction was not committed pre-start: {match_id}")

            selected_player = str(prediction.get("selected_player", ""))
            if selected_player != str(entry.get("selected_player", "")):
                raise ValueError(f"scorecard selected player mismatch: {match_id}")
            if selected_player == fixture.get("player_a"):
                selected_probability = float(prediction["p_player_a"])
            elif selected_player == fixture.get("player_b"):
                selected_probability = float(prediction["p_player_b"])
            else:
                raise ValueError(f"selected player is outside fixture identity: {match_id}")

            scorecard_probability = float(entry.get("selected_probability"))
            if not (
                math.isfinite(scorecard_probability)
                and abs(scorecard_probability - selected_probability) <= 1e-12
            ):
                raise ValueError(f"scorecard selected probability mismatch: {match_id}")

            baseline: dict[str, Any] | None = None
            baseline_path_raw = str(entry.get("baseline_path", "")).strip()
            if baseline_path_raw:
                baseline_path = _repo_path(
                    repo_root,
                    baseline_path_raw,
                    prefix="web-shadow",
                )
                expected_baseline_root = slate_root / "baselines"
                try:
                    baseline_path.relative_to(expected_baseline_root)
                except ValueError as exc:
                    raise ValueError(
                        f"baseline is outside its immutable slate directory: {match_id}"
                    ) from exc
                baseline = _load_json(baseline_path)
                if baseline.get("schema_version") != _BASELINE_SCHEMA:
                    raise ValueError(f"unsupported baseline schema: {match_id}")
                if baseline.get("record_type") != "WEB_SHADOW_BASELINE":
                    raise ValueError(f"unexpected baseline record type: {match_id}")
                if baseline.get("baseline_name") != _BASELINE_NAME:
                    raise ValueError(f"unexpected baseline name: {match_id}")
                if baseline.get("production_eligible") is not False:
                    raise ValueError(f"baseline escaped non-production isolation: {match_id}")
                _assert_record_digest(baseline, label=f"baseline {match_id}")
                if baseline.get("slate_id") != slate_id:
                    raise ValueError(f"baseline slate identity mismatch: {match_id}")
                if baseline.get("match_id") != match_id:
                    raise ValueError(f"baseline match identity mismatch: {match_id}")
                if baseline.get("prediction_record_sha256") != observed_sha:
                    raise ValueError(f"baseline prediction SHA mismatch: {match_id}")
                if int(baseline.get("artifact_id", -1)) != int(
                    receipt.get("workflow_artifact_id", -2)
                ):
                    raise ValueError(f"baseline artifact ID mismatch: {match_id}")
                if baseline.get("artifact_sha256") != receipt.get(
                    "workflow_artifact_sha256"
                ):
                    raise ValueError(f"baseline artifact SHA mismatch: {match_id}")

                matchup_sha = str(baseline.get("matchup_input_sha256", "")).strip()
                if len(matchup_sha) != 64:
                    raise ValueError(f"baseline matchup input SHA is invalid: {match_id}")
                try:
                    int(matchup_sha, 16)
                except ValueError as exc:
                    raise ValueError(
                        f"baseline matchup input SHA is invalid: {match_id}"
                    ) from exc

                elo_logit = float(baseline.get("elo_logit"))
                if not math.isfinite(elo_logit):
                    raise ValueError(f"baseline Elo logit is invalid: {match_id}")
                expected_baseline_p_a = 1.0 / (1.0 + math.exp(-elo_logit))
                baseline_p_a = float(baseline.get("p_player_a"))
                baseline_p_b = float(baseline.get("p_player_b"))
                if not (
                    math.isfinite(baseline_p_a)
                    and math.isfinite(baseline_p_b)
                    and abs(baseline_p_a - expected_baseline_p_a) <= 1e-12
                    and abs(baseline_p_b - (1.0 - expected_baseline_p_a)) <= 1e-12
                ):
                    raise ValueError(f"baseline probability mismatch: {match_id}")

                expected_baseline_player = (
                    str(fixture.get("player_a"))
                    if baseline_p_a >= 0.5
                    else str(fixture.get("player_b"))
                )
                if baseline.get("selected_player") != expected_baseline_player:
                    raise ValueError(f"baseline selected player mismatch: {match_id}")
                baseline_count += 1

            if status == "PENDING":
                forbidden_settlement_fields = {
                    "settlement_path",
                    "settlement_record_sha256",
                    "result_record_sha256",
                }.intersection(entry)
                if forbidden_settlement_fields:
                    raise ValueError(
                        f"pending scorecard entry already has settlement evidence: {match_id}"
                    )
                pending += 1
                continue

            settlement_path_raw = str(entry.get("settlement_path", "")).strip()
            if not settlement_path_raw:
                raise ValueError(f"settled scorecard entry lacks settlement: {match_id}")
            settlement_path = _repo_path(
                repo_root,
                settlement_path_raw,
                prefix="web-shadow",
            )
            expected_settlement_root = slate_root / "settlements"
            try:
                settlement_path.relative_to(expected_settlement_root)
            except ValueError as exc:
                raise ValueError(
                    f"settlement is outside its immutable slate directory: {match_id}"
                ) from exc

            settlement = _load_json(settlement_path)
            if settlement.get("record_type") != "WEB_SHADOW_SETTLEMENT":
                raise ValueError(f"unexpected settlement type: {match_id}")
            if settlement.get("production_eligible") is not False:
                raise ValueError(f"settlement escaped non-production isolation: {match_id}")
            settlement_sha = _assert_record_digest(
                settlement,
                label=f"settlement {match_id}",
            )
            if settlement_sha != str(entry.get("settlement_record_sha256", "")):
                raise ValueError(f"scorecard settlement SHA mismatch: {match_id}")
            if settlement.get("prediction_record_sha256") != observed_sha:
                raise ValueError(f"settlement prediction SHA mismatch: {match_id}")
            if settlement.get("match_id") != match_id:
                raise ValueError(f"settlement match identity mismatch: {match_id}")

            winner = str(settlement.get("winner", ""))
            player_a = str(fixture.get("player_a", ""))
            player_b = str(fixture.get("player_b", ""))
            if winner not in {player_a, player_b}:
                raise ValueError(f"settlement winner is outside fixture: {match_id}")
            expected_correct = winner == selected_player
            if settlement.get("prediction_correct") is not expected_correct:
                raise ValueError(f"settlement correctness mismatch: {match_id}")

            result_observed_at = datetime.fromisoformat(
                str(settlement.get("result_observed_at", ""))
            )
            if result_observed_at.tzinfo is None:
                raise ValueError(f"settlement observation must be timezone-aware: {match_id}")
            if result_observed_at <= scheduled_start:
                raise ValueError(f"settlement observation is not post-start: {match_id}")

            result_path_raw = str(settlement.get("result_record_path", "")).strip()
            result_path = _repo_path(repo_root, result_path_raw, prefix="web-shadow")
            result_parts = Path(result_path_raw).parts
            if len(result_parts) != 3 or result_parts[:2] != (
                "web-shadow",
                "results",
            ):
                raise ValueError(f"settlement result path is outside results: {match_id}")
            result_sha = _sha256_file(result_path)
            if result_sha != str(entry.get("result_record_sha256", "")):
                raise ValueError(f"scorecard result SHA mismatch: {match_id}")
            result = _load_json(result_path)
            if result.get("production_eligible") is not False:
                raise ValueError(f"result escaped non-production isolation: {match_id}")
            expected_result_values = {
                "match_id": match_id,
                "expected_prediction_record_sha256": observed_sha,
                "winner": winner,
                "status": settlement.get("status"),
                "result_source_url": settlement.get("result_source_url"),
                "result_observed_at": settlement.get("result_observed_at"),
            }
            for key, value in expected_result_values.items():
                if result.get(key) != value:
                    raise ValueError(f"result evidence mismatch for {key}: {match_id}")
            if not str(result.get("score", "")).strip():
                raise ValueError(f"result evidence lacks score: {match_id}")

            settled += 1
            slate_settled += 1

            settlement_status = str(settlement.get("status", "")).strip().upper()
            if settlement_status != "COMPLETED":
                continue

            genome_metric_row = {
                "p_player_a": float(prediction["p_player_a"]),
                "p_player_b": float(prediction["p_player_b"]),
                "selected_probability": selected_probability,
                "actual_player_a_won": winner == player_a,
                "prediction_correct": expected_correct,
            }
            metric_rows.append(genome_metric_row)
            if baseline is not None:
                baseline_genome_metric_rows.append(genome_metric_row)
                baseline_p_a = float(baseline["p_player_a"])
                baseline_p_b = float(baseline["p_player_b"])
                baseline_selected_player = str(baseline["selected_player"])
                baseline_metric_rows.append(
                    {
                        "p_player_a": baseline_p_a,
                        "p_player_b": baseline_p_b,
                        "selected_probability": max(baseline_p_a, baseline_p_b),
                        "actual_player_a_won": winner == player_a,
                        "prediction_correct": winner == baseline_selected_player,
                    }
                )

        expected_slate_status = (
            "SETTLED"
            if slate_settled == len(predictions)
            else "PENDING_SETTLEMENT"
        )
        if slate.get("status") != expected_slate_status:
            raise ValueError(f"slate settlement status mismatch: {slate_id}")

    if int(scorecard.get("official_slate_count", -1)) != len(slates):
        raise ValueError("official slate count does not match scorecard contents")
    if int(scorecard.get("pending_match_count", -1)) != pending:
        raise ValueError("pending match count does not match scorecard contents")
    if int(scorecard.get("settled_match_count", -1)) != settled:
        raise ValueError("settled match count does not match scorecard contents")

    if metric_rows:
        expected_metrics = _compute_metrics(metric_rows)
        observed_metrics = scorecard.get("metrics")
        _assert_metric_payload(
            expected_metrics,
            observed_metrics,
            path="metrics",
        )
    elif "metrics" in scorecard:
        raise ValueError(
            "scorecard cannot publish metrics without completed settlements"
        )

    if baseline_metric_rows:
        expected_comparison = _compute_baseline_comparison(
            genome_rows=baseline_genome_metric_rows,
            baseline_rows=baseline_metric_rows,
        )
        _assert_metric_payload(
            expected_comparison,
            scorecard.get("baseline_comparison"),
            path="baseline_comparison",
        )
    elif "baseline_comparison" in scorecard:
        raise ValueError(
            "scorecard cannot publish baseline comparison without settled baselines"
        )

    if baseline_count != int(scorecard.get("baseline_match_count", 0)):
        raise ValueError("baseline match count does not match scorecard contents")

    return {
        "official_slate_count": len(slates),
        "official_match_count": len(seen_match_ids),
        "pending_match_count": pending,
        "settled_match_count": settled,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the official non-production Web Shadow scorecard"
    )
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=Path("web-shadow/scorecard.json"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = validate_web_shadow_scorecard(
        scorecard_path=args.scorecard,
        repo_root=args.repo_root,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
