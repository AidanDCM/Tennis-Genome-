from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tennis_genome.evaluation.metrics import binary_log_loss, brier_score
from tennis_genome.experiments.pattern_confirm import (
    HYPOTHESES,
    market_core_probability,
    verify_fit_payload,
)

_EXPERIMENT_ID = "PATTERN-CONFIRM-001-BASELINE-TRANSFER-AUDIT"
_VERSION = "pattern-confirm-baseline-transfer-v1"
_VALIDATION_YEARS = {2023, 2024, 2025}


@dataclass(frozen=True)
class TransferClaimAudit:
    hypothesis_id: str
    source_candidate_id: str
    n: int
    original_mean_residual: float
    pooled_mean_residual: float
    residual_delta: float
    original_bootstrap_lower: float
    original_bootstrap_upper: float
    same_direction: bool
    pooled_mean_inside_original_interval: bool
    pooled_baseline_brier: float
    corrected_brier: float
    brier_improvement: float
    pooled_baseline_log_loss: float
    corrected_log_loss: float
    log_loss_improvement: float
    proper_scores_improve: bool
    transfer_compatible: bool


@dataclass(frozen=True)
class TransferAuditReport:
    experiment_id: str
    version: str
    outcome_scope: str
    discovery_artifact_sha256: str
    feature_ledger_sha256: str
    residual_ledger_sha256: str
    market_core_fit_sha256: str
    claims: tuple[TransferClaimAudit, ...]
    all_transfer_compatible: bool
    artifact_sha256: str


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _payload_sha(payload: object) -> str:
    return _sha256_bytes(_canonical_json(payload))


def _self_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _payload_sha(unsigned)


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("JSONL rows must be objects")
        rows.append(value)
    return rows


def _candidate_map(summary: dict[str, object]) -> dict[str, dict[str, object]]:
    survivors = summary.get("survivors")
    if not isinstance(survivors, list):
        raise ValueError("discovery summary missing survivors")
    result: dict[str, dict[str, object]] = {}
    for raw in survivors:
        if not isinstance(raw, dict):
            raise ValueError("discovery survivor must be an object")
        candidate_id = str(raw.get("candidate_id", ""))
        if not candidate_id or candidate_id in result:
            raise ValueError("discovery survivor IDs must be unique and non-empty")
        result[candidate_id] = raw
    return result


def _clip_probability(value: float) -> float:
    return min(max(float(value), 1e-6), 1.0 - 1e-6)


def build_transfer_audit(
    *,
    feature_ledger_path: Path,
    residual_ledger_path: Path,
    discovery_summary_path: Path,
    fit_path: Path,
) -> TransferAuditReport:
    summary = json.loads(discovery_summary_path.read_text())
    fit_payload = json.loads(fit_path.read_text())
    if not isinstance(summary, dict) or not isinstance(fit_payload, dict):
        raise ValueError("summary and fit must be JSON objects")
    if summary.get("experiment_id") != "PATTERN-DISCOVERY-001":
        raise ValueError("unexpected discovery experiment ID")

    features = _load_jsonl(feature_ledger_path)
    residuals = _load_jsonl(residual_ledger_path)
    feature_sha = _payload_sha(features)
    residual_sha = _payload_sha(residuals)
    if feature_sha != str(summary.get("feature_ledger_sha256", "")):
        raise ValueError("feature ledger canonical payload hash does not match discovery summary")
    if residual_sha != str(summary.get("residual_ledger_sha256", "")):
        raise ValueError("residual ledger canonical payload hash does not match discovery summary")

    fit = verify_fit_payload(fit_payload)
    feature_by_id = {str(row.get("match_id", "")): row for row in features}
    residual_by_id = {str(row.get("match_id", "")): row for row in residuals}
    if (
        len(feature_by_id) != len(features)
        or len(residual_by_id) != len(residuals)
        or set(feature_by_id) != set(residual_by_id)
    ):
        raise ValueError("discovery ledgers require unique identical match IDs")

    candidate_by_id = _candidate_map(summary)
    claims: list[TransferClaimAudit] = []
    for hypothesis in HYPOTHESES:
        candidate = candidate_by_id.get(hypothesis.source_candidate_id)
        if candidate is None:
            raise ValueError(f"missing discovery candidate {hypothesis.source_candidate_id}")

        selected: list[tuple[dict[str, object], dict[str, object]]] = []
        for match_id, feature in feature_by_id.items():
            if str(feature.get("tour")) != "ATP":
                continue
            if int(feature.get("year")) not in _VALIDATION_YEARS:
                continue
            gap = float(feature.get("profile_gap"))
            if hypothesis.rule == "profile_gap_lt":
                member = gap < hypothesis.threshold
            elif hypothesis.rule == "abs_profile_gap_ge":
                member = abs(gap) >= hypothesis.threshold
            else:
                raise ValueError(f"unsupported hypothesis rule {hypothesis.rule}")
            if member:
                selected.append((feature, residual_by_id[match_id]))

        expected_n = int(candidate.get("validation_n"))
        if len(selected) != expected_n:
            raise ValueError(
                f"validation population mismatch for {hypothesis.hypothesis_id}: "
                f"expected {expected_n}, got {len(selected)}"
            )

        outcomes: list[bool] = []
        original_probabilities: list[float] = []
        pooled_probabilities: list[float] = []
        for feature, residual in selected:
            outcome = bool(residual.get("outcome_a"))
            original_probability = float(residual.get("market_core_probability_a"))
            pooled_probability = market_core_probability(
                float(feature.get("market_probability_a")),
                float(feature.get("core_probability_a")),
                fit,
            )
            outcomes.append(outcome)
            original_probabilities.append(original_probability)
            pooled_probabilities.append(pooled_probability)

        original_residuals = [
            (1.0 if outcome else 0.0) - probability
            for outcome, probability in zip(outcomes, original_probabilities, strict=True)
        ]
        pooled_residuals = [
            (1.0 if outcome else 0.0) - probability
            for outcome, probability in zip(outcomes, pooled_probabilities, strict=True)
        ]
        original_mean = sum(original_residuals) / len(original_residuals)
        pooled_mean = sum(pooled_residuals) / len(pooled_residuals)
        stated_original = float(candidate.get("validation_mean_residual"))
        if abs(original_mean - stated_original) > 1e-12:
            raise ValueError("original validation residual does not reproduce")

        bootstrap = candidate.get("validation_bootstrap")
        if not isinstance(bootstrap, dict):
            raise ValueError("candidate missing validation bootstrap")
        lower = float(bootstrap.get("lower"))
        upper = float(bootstrap.get("upper"))
        same_direction = (original_mean < 0.0 and pooled_mean < 0.0) or (
            original_mean > 0.0 and pooled_mean > 0.0
        )
        inside = lower <= pooled_mean <= upper

        corrected = [
            _clip_probability(probability + hypothesis.correction)
            for probability in pooled_probabilities
        ]
        baseline_brier = brier_score(outcomes, pooled_probabilities)
        corrected_brier = brier_score(outcomes, corrected)
        baseline_log_loss = binary_log_loss(outcomes, pooled_probabilities)
        corrected_log_loss = binary_log_loss(outcomes, corrected)
        brier_improvement = baseline_brier - corrected_brier
        log_loss_improvement = baseline_log_loss - corrected_log_loss
        score_gate = brier_improvement > 0.0 and log_loss_improvement > 0.0
        compatible = bool(same_direction and inside and score_gate)

        claims.append(
            TransferClaimAudit(
                hypothesis_id=hypothesis.hypothesis_id,
                source_candidate_id=hypothesis.source_candidate_id,
                n=len(selected),
                original_mean_residual=original_mean,
                pooled_mean_residual=pooled_mean,
                residual_delta=pooled_mean - original_mean,
                original_bootstrap_lower=lower,
                original_bootstrap_upper=upper,
                same_direction=same_direction,
                pooled_mean_inside_original_interval=inside,
                pooled_baseline_brier=baseline_brier,
                corrected_brier=corrected_brier,
                brier_improvement=brier_improvement,
                pooled_baseline_log_loss=baseline_log_loss,
                corrected_log_loss=corrected_log_loss,
                log_loss_improvement=log_loss_improvement,
                proper_scores_improve=score_gate,
                transfer_compatible=compatible,
            )
        )

    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "outcome_scope": "spent 2023-2025 internal validation only; no prospective outcomes",
        "discovery_artifact_sha256": str(summary.get("artifact_sha256")),
        "feature_ledger_sha256": feature_sha,
        "residual_ledger_sha256": residual_sha,
        "market_core_fit_sha256": fit.artifact_sha256,
        "claims": [asdict(claim) for claim in claims],
        "all_transfer_compatible": all(claim.transfer_compatible for claim in claims),
    }
    digest = _self_hash(unsigned)
    return TransferAuditReport(
        experiment_id=_EXPERIMENT_ID,
        version=_VERSION,
        outcome_scope=str(unsigned["outcome_scope"]),
        discovery_artifact_sha256=str(unsigned["discovery_artifact_sha256"]),
        feature_ledger_sha256=feature_sha,
        residual_ledger_sha256=residual_sha,
        market_core_fit_sha256=fit.artifact_sha256,
        claims=tuple(claims),
        all_transfer_compatible=bool(unsigned["all_transfer_compatible"]),
        artifact_sha256=digest,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit PATTERN-CONFIRM-001 baseline transfer")
    parser.add_argument("--feature-ledger", required=True, type=Path)
    parser.add_argument("--residual-ledger", required=True, type=Path)
    parser.add_argument("--discovery-summary", required=True, type=Path)
    parser.add_argument("--fit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = build_transfer_audit(
        feature_ledger_path=args.feature_ledger,
        residual_ledger_path=args.residual_ledger,
        discovery_summary_path=args.discovery_summary,
        fit_path=args.fit,
    )
    args.output.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    if not report.all_transfer_compatible:
        raise SystemExit("baseline transfer compatibility audit failed")


if __name__ == "__main__":
    main()
