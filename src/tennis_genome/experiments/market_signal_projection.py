from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_PROJECTION_VERSION = "market-signal-projection-v2"

SignalName = Literal["profile_gap", "genome"]
Tour = Literal["ATP", "WTA"]


@dataclass(frozen=True)
class ProjectionSpec:
    name: str
    experiment_id: str
    tour: Tour
    signal_name: SignalName
    signal_field: str
    core_probability_field: str
    expected_parent_sha256: str


_FROZEN_SPECS: dict[str, ProjectionSpec] = {
    "atp_profile_gap": ProjectionSpec(
        name="atp_profile_gap",
        experiment_id="PROFILE-GAP-001",
        tour="ATP",
        signal_name="profile_gap",
        signal_field="profile_gap_match",
        core_probability_field="strict_core_probability",
        expected_parent_sha256="532ff66304914f0962e5747f20790916c70e082efedba695d26717632db946fd",
    ),
    "wta_profile_gap": ProjectionSpec(
        name="wta_profile_gap",
        experiment_id="PROFILE-GAP-001",
        tour="WTA",
        signal_name="profile_gap",
        signal_field="profile_gap_match",
        core_probability_field="strict_core_probability",
        expected_parent_sha256="343903af5f53cd1d519ebafdabf6ddb2dd0645847ff77e1820a156caf012bc55",
    ),
    "atp_genome": ProjectionSpec(
        name="atp_genome",
        experiment_id="GENOME-ADV-001",
        tour="ATP",
        signal_name="genome",
        signal_field="full_neighbor_residual",
        core_probability_field="core_probability_a",
        expected_parent_sha256="37671b15b4f7bb4db98767f09a10f57dd43eb61baeacd2aed0713e8a67b298fa",
    ),
    "wta_genome": ProjectionSpec(
        name="wta_genome",
        experiment_id="GENOME-ADV-001",
        tour="WTA",
        signal_name="genome",
        signal_field="core_neighbor_residual",
        core_probability_field="core_probability_a",
        expected_parent_sha256="08df00ce43bed558f8d479f14e74bdb05504864ab0c4310aa3f3979029d0e2a3",
    ),
}


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def project_signal_report(
    input_path: str | Path,
    *,
    spec: ProjectionSpec,
) -> dict[str, object]:
    """Project one accepted report into a result-free signal/Core ledger."""

    parent_path = Path(input_path)
    parent_sha = _sha256_file(parent_path)
    expected = spec.expected_parent_sha256.lower()
    if not _valid_sha256(expected):
        raise ValueError("projection spec expected_parent_sha256 is invalid")
    if parent_sha != expected:
        raise ValueError(
            f"{spec.name} parent SHA-256 mismatch: expected {expected}, got {parent_sha}"
        )

    payload = json.loads(parent_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("signal parent artifact must be a JSON object")
    if payload.get("experiment_id") != spec.experiment_id:
        raise ValueError("signal parent experiment_id differs from frozen projection spec")
    if payload.get("tour") != spec.tour:
        raise ValueError("signal parent tour differs from frozen projection spec")
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise ValueError("signal parent artifact lacks predictions list")

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in predictions:
        if not isinstance(row, dict):
            raise ValueError("signal parent contains an invalid prediction row")
        match_id = str(row.get("match_id", "")).strip()
        if not match_id:
            raise ValueError("signal projection encountered an empty match_id")
        if match_id in seen:
            raise ValueError(f"signal projection encountered duplicate match_id {match_id}")
        seen.add(match_id)
        if spec.signal_field not in row:
            raise ValueError(f"signal parent row lacks frozen field {spec.signal_field}")
        if spec.core_probability_field not in row:
            raise ValueError(f"signal parent row lacks frozen field {spec.core_probability_field}")
        try:
            signal = float(row[spec.signal_field])
            core_probability = float(row[spec.core_probability_field])
        except (TypeError, ValueError) as exc:
            raise ValueError("signal projection values must be numeric") from exc
        if not math.isfinite(signal):
            raise ValueError("signal projection value must be finite")
        if not math.isfinite(core_probability) or not 0.0 < core_probability < 1.0:
            raise ValueError("Core probability must be finite and in (0, 1)")
        rows.append(
            {
                "match_id": match_id,
                spec.signal_field: signal,
                spec.core_probability_field: core_probability,
            }
        )

    rows.sort(key=lambda row: str(row["match_id"]))
    unsigned: dict[str, object] = {
        "projection_version": _PROJECTION_VERSION,
        "source_artifact_sha256": parent_sha,
        "source_experiment_id": spec.experiment_id,
        "experiment_id": spec.experiment_id,
        "tour": spec.tour,
        "signal_name": spec.signal_name,
        "signal_field": spec.signal_field,
        "core_probability_field": spec.core_probability_field,
        "predictions": rows,
    }
    artifact_sha = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return {**unsigned, "artifact_sha256": artifact_sha}


def write_projection(payload: dict[str, object], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create frozen market signal/Core projections")
    parser.add_argument("--spec", required=True, choices=sorted(_FROZEN_SPECS))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = project_signal_report(args.input, spec=_FROZEN_SPECS[args.spec])
    write_projection(payload, args.output)
    print(
        json.dumps(
            {
                "projection_version": payload["projection_version"],
                "experiment_id": payload["experiment_id"],
                "tour": payload["tour"],
                "signal_name": payload["signal_name"],
                "signal_field": payload["signal_field"],
                "core_probability_field": payload["core_probability_field"],
                "source_artifact_sha256": payload["source_artifact_sha256"],
                "artifact_sha256": payload["artifact_sha256"],
                "row_count": len(payload["predictions"]),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
