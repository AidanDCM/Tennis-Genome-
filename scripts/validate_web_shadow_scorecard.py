from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


_SCORECARD_SCHEMA = "tennis-genome-web-shadow-scorecard-v1"
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

            observed_sha = str(prediction.get("record_sha256", ""))
            unsigned = dict(prediction)
            unsigned.pop("record_sha256", None)
            if _canonical_sha256(unsigned) != observed_sha:
                raise ValueError(f"prediction record digest mismatch: {match_id}")
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

            if status == "PENDING":
                if "settlement_path" in entry:
                    raise ValueError(
                        f"pending scorecard entry already has a settlement: {match_id}"
                    )
                pending += 1
            else:
                settlement_path = str(entry.get("settlement_path", "")).strip()
                if not settlement_path:
                    raise ValueError(f"settled scorecard entry lacks settlement: {match_id}")
                settlement = _load_json(
                    _repo_path(repo_root, settlement_path, prefix="web-shadow")
                )
                if settlement.get("record_type") != "WEB_SHADOW_SETTLEMENT":
                    raise ValueError(f"unexpected settlement type: {match_id}")
                if settlement.get("prediction_record_sha256") != observed_sha:
                    raise ValueError(f"settlement prediction SHA mismatch: {match_id}")
                settled += 1

    if int(scorecard.get("official_slate_count", -1)) != len(slates):
        raise ValueError("official slate count does not match scorecard contents")
    if int(scorecard.get("pending_match_count", -1)) != pending:
        raise ValueError("pending match count does not match scorecard contents")
    if int(scorecard.get("settled_match_count", -1)) != settled:
        raise ValueError("settled match count does not match scorecard contents")

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
