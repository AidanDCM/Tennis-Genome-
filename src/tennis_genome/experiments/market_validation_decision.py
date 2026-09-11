from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tennis_genome.evaluation.metrics import calibration_bins

_EXPERIMENT_ID = "MARKET-VALIDATION-DECISION-001"
_REQUIRED_LABELS = {
    "ATP:profile_gap",
    "WTA:profile_gap",
    "ATP:genome",
    "WTA:genome",
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


def _load_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("validation result bundle must be a JSON object")
    return payload


def _claim_label(claim: dict[str, Any]) -> str:
    return f"{claim.get('tour', '')}:{claim.get('signal_name', '')}"


def _claims_by_label(family: dict[str, Any], *, label: str) -> dict[str, dict[str, Any]]:
    claims = family.get("claims")
    if not isinstance(claims, list):
        raise ValueError(f"{label} family lacks claims list")
    result: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError(f"{label} family contains invalid claim")
        key = _claim_label(claim)
        if key in result:
            raise ValueError(f"{label} family contains duplicate claim {key}")
        result[key] = claim
    if set(result) != _REQUIRED_LABELS:
        raise ValueError(f"{label} family claim set differs from frozen four-claim design")
    return result


def _decisions_by_label(
    family: dict[str, Any],
    *,
    pass_field: str,
    label: str,
) -> dict[str, bool]:
    rows = family.get("decisions")
    if not isinstance(rows, list):
        raise ValueError(f"{label} family lacks decisions list")
    result: dict[str, bool] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} family contains invalid decision")
        key = str(row.get("label", ""))
        if key in result:
            raise ValueError(f"{label} family contains duplicate decision {key}")
        value = row.get(pass_field)
        if not isinstance(value, bool):
            raise ValueError(f"{label} decision {key} lacks boolean {pass_field}")
        result[key] = value
    if set(result) != _REQUIRED_LABELS:
        raise ValueError(f"{label} decision set differs from frozen four-claim design")
    return result


def _reliability(
    predictions: list[dict[str, Any]],
    *,
    probability_fields: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    if not predictions:
        raise ValueError("reliability diagnostics require non-empty predictions")
    outcomes: list[bool] = []
    probabilities: dict[str, list[float]] = {name: [] for name in probability_fields}
    for row in predictions:
        if not isinstance(row, dict):
            raise ValueError("prediction row must be an object")
        if not isinstance(row.get("outcome_a"), bool):
            raise ValueError("prediction row lacks boolean outcome_a")
        outcomes.append(bool(row["outcome_a"]))
        for field in probability_fields:
            try:
                value = float(row[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"prediction row lacks numeric {field}") from exc
            probabilities[field].append(value)
    return {
        field: [asdict(bucket) for bucket in calibration_bins(outcomes, values, n_bins=10)]
        for field, values in probabilities.items()
    }


def build_validation_decision_artifact(
    result_bundle_path: str | Path,
) -> dict[str, object]:
    bundle = _load_object(result_bundle_path)
    if bundle.get("experiment_id") != "MARKET-VALIDATION-BOOK-RUN-001":
        raise ValueError("unexpected validation bundle experiment_id")
    if bundle.get("outcome_open") is not True:
        raise ValueError("combined decision requires completed Stage B bundle")

    primary_artifact = bundle.get("market_edge_001")
    adversarial_artifact = bundle.get("market_edge_adv_001")
    if not isinstance(primary_artifact, dict) or not isinstance(adversarial_artifact, dict):
        raise ValueError("Stage B bundle lacks both frozen market artifacts")

    primary_family = primary_artifact.get("family_report")
    adversarial_family = adversarial_artifact.get("family_report")
    if not isinstance(primary_family, dict) or not isinstance(adversarial_family, dict):
        raise ValueError("market artifacts lack family reports")

    primary_claims = _claims_by_label(primary_family, label="MARKET-EDGE-001")
    adversarial_claims = _claims_by_label(adversarial_family, label="MARKET-EDGE-ADV-001")
    primary_decisions = _decisions_by_label(
        primary_family,
        pass_field="market_incremental_pass",
        label="MARKET-EDGE-001",
    )
    adversarial_decisions = _decisions_by_label(
        adversarial_family,
        pass_field="market_core_incremental_pass",
        label="MARKET-EDGE-ADV-001",
    )

    combined: list[dict[str, object]] = []
    diagnostics: dict[str, object] = {}
    for key in sorted(_REQUIRED_LABELS):
        primary_claim = primary_claims[key]
        adversarial_claim = adversarial_claims[key]
        primary_predictions = primary_claim.get("predictions")
        if not isinstance(primary_predictions, list):
            raise ValueError(f"{key} primary claim lacks predictions")
        adversarial_primary = adversarial_claim.get("primary")
        if not isinstance(adversarial_primary, dict):
            raise ValueError(f"{key} adversarial claim lacks primary window")
        adversarial_predictions = adversarial_primary.get("predictions")
        if not isinstance(adversarial_predictions, list):
            raise ValueError(f"{key} adversarial primary window lacks predictions")

        primary_pass = primary_decisions[key]
        adversarial_pass = adversarial_decisions[key]
        combined.append(
            {
                "label": key,
                "market_incremental_pass": primary_pass,
                "market_core_incremental_pass": adversarial_pass,
                "stack_promotion_pass": bool(primary_pass and adversarial_pass),
            }
        )
        diagnostics[key] = {
            "market_edge_001": _reliability(
                primary_predictions,
                probability_fields=(
                    "market_probability_a",
                    "control_probability_a",
                    "challenger_probability_a",
                ),
            ),
            "market_edge_adv_001": _reliability(
                adversarial_predictions,
                probability_fields=(
                    "market_probability_a",
                    "core_probability_a",
                    "market_only_probability_a",
                    "market_core_probability_a",
                    "challenger_probability_a",
                ),
            ),
        }

    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "source_validation_bundle_sha256": _sha256_file(result_bundle_path),
        "rule": "stack_promotion_pass = market_incremental_pass AND market_core_incremental_pass",
        "reliability_bins": "fixed_width_10_bins_full_population_diagnostic_only",
        "decisions": combined,
        "diagnostics": diagnostics,
    }
    artifact_sha = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return {**unsigned, "artifact_sha256": artifact_sha}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine frozen market decisions and emit reliability diagnostics"
    )
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = build_validation_decision_artifact(args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
