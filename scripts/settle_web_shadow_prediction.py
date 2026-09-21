from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tennis_genome.prospective.web_shadow import settle_web_shadow, write_record


def settle_from_result_file(
    *,
    result_path: Path,
    output_path: Path,
) -> dict[str, object]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result JSON must contain an object")

    prediction_path_raw = str(result.get("prediction_path", "")).strip()
    if not prediction_path_raw:
        raise ValueError("result must bind a prediction_path")
    prediction_path = Path(prediction_path_raw)
    if prediction_path.is_absolute() or ".." in prediction_path.parts:
        raise ValueError("prediction_path must be a repository-relative path")
    parts = prediction_path.parts
    legacy_prediction = (
        len(parts) == 3
        and parts[:2] == ("web-shadow", "predictions")
    )
    official_slate_prediction = (
        len(parts) == 5
        and parts[0] == "web-shadow"
        and parts[1] == "slates"
        and parts[3] == "predictions"
    )
    if not (legacy_prediction or official_slate_prediction):
        raise ValueError(
            "prediction_path must be a legacy web-shadow prediction or an "
            "official run-scoped slate prediction"
        )
    if not prediction_path.is_file():
        raise FileNotFoundError(f"prediction record is missing: {prediction_path}")

    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    if not isinstance(prediction, dict):
        raise ValueError("prediction JSON must contain an object")

    expected_sha = str(result.get("expected_prediction_record_sha256", "")).strip()
    if expected_sha != str(prediction.get("record_sha256", "")):
        raise ValueError("result prediction SHA does not match frozen prediction record")

    settlement = settle_web_shadow(
        prediction,
        winner=str(result.get("winner", "")).strip(),
        status=str(result.get("status", "")).strip(),
        result_source_url=str(result.get("result_source_url", "")).strip(),
        result_observed_at=str(result.get("result_observed_at", "")).strip(),
    )
    settlement["result_record_path"] = result_path.as_posix()
    settlement["production_eligible"] = False

    unsigned = dict(settlement)
    unsigned.pop("record_sha256")
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    settlement["record_sha256"] = hashlib.sha256(canonical).hexdigest()
    write_record(output_path, settlement)
    return settlement


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Settle a frozen Web Shadow prediction from a committed public result"
    )
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settlement = settle_from_result_file(
        result_path=args.result,
        output_path=args.output,
    )
    print(json.dumps(settlement, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
