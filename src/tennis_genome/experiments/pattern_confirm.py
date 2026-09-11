from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from tennis_genome.evaluation.metrics import binary_log_loss, brier_score

_EXPERIMENT_ID = "PATTERN-CONFIRM-001"
_VERSION = "pattern-confirm-v1"
_PROSPECTIVE_CUTOFF = "2026-09-12T00:00:00-04:00"
_LOGIT_CLIP = 1e-6
_FAMILY_ALPHA = 0.05
_CLAIM_ALPHA = 0.025
_TARGET_POWER = 0.90
_OBF_CONSTANT = 2.0243208652402602
_OBF_BOUNDARIES = (
    4.0486417304805205,
    2.862822022035254,
    2.337484394530551,
    2.0243208652402602,
)
_RESULT_FIELD_TOKENS = (
    "outcome",
    "winner",
    "result",
    "score",
    "settled",
    "retirement",
    "walkover",
)

ConfirmationStatus = Literal["ACCUMULATING", "CONFIRMED", "FAILED_TO_CONFIRM"]


@dataclass(frozen=True)
class PatternHypothesis:
    hypothesis_id: str
    source_candidate_id: str
    rule: str
    threshold: float
    correction: float
    planning_effect: float
    planning_sd: float
    max_n: int
    look_ns: tuple[int, int, int, int]
    z_boundaries: tuple[float, float, float, float]


HYPOTHESES = (
    PatternHypothesis(
        hypothesis_id="PC-ATP-PG-LOW",
        source_candidate_id="ATP:single_variable:0914faa2399d38c4",
        rule="profile_gap_lt",
        threshold=-0.4045998117259577,
        correction=-0.031143878674067826,
        planning_effect=0.031143878674067826,
        planning_sd=0.4347784219646229,
        max_n=2094,
        look_ns=(524, 1047, 1570, 2094),
        z_boundaries=_OBF_BOUNDARIES,
    ),
    PatternHypothesis(
        hypothesis_id="PC-ATP-PG-ABS-HIGH",
        source_candidate_id="ATP:uncertainty_ood:90451092e0e9a458",
        rule="abs_profile_gap_ge",
        threshold=0.47108555150900466,
        correction=-0.022734415112664306,
        planning_effect=0.022734415112664306,
        planning_sd=0.42442004311667597,
        max_n=3744,
        look_ns=(936, 1872, 2808, 3744),
        z_boundaries=_OBF_BOUNDARIES,
    ),
)


@dataclass(frozen=True)
class FrozenMarketCoreFit:
    experiment_id: str
    version: str
    source_bundle_sha256: str
    source_claim: str
    training_rows_sha256: str
    training_n: int
    training_start_year: int
    training_end_year: int
    intercept: float
    market_logit_slope: float
    core_logit_slope: float
    artifact_sha256: str


@dataclass(frozen=True)
class ProspectiveRecord:
    experiment_id: str
    version: str
    match_id: str
    tour: str
    scheduled_start: str
    observed_at: str
    market_source: str
    market_probability_a: float
    core_probability_a: float
    profile_gap: float
    market_core_probability_a: float
    market_core_fit_sha256: str
    matched_hypotheses: tuple[str, ...]
    source_row_sha256: str
    record_sha256: str


@dataclass(frozen=True)
class SettledOutcome:
    match_id: str
    outcome_a: bool | None
    retirement: bool
    walkover: bool


@dataclass(frozen=True)
class LookResult:
    look_index: int
    n: int
    z: float
    boundary: float
    mean_residual: float
    sample_sd: float
    baseline_brier: float
    corrected_brier: float
    brier_improvement: float
    baseline_log_loss: float
    corrected_log_loss: float
    log_loss_improvement: float
    efficacy_boundary_crossed: bool
    proper_score_gate: bool
    confirmed_at_look: bool


@dataclass(frozen=True)
class HypothesisReport:
    hypothesis_id: str
    source_candidate_id: str
    available_qualifying_n: int
    excluded_retirement_n: int
    excluded_walkover_n: int
    status: ConfirmationStatus
    confirmed_look: int | None
    completed_looks: tuple[LookResult, ...]


@dataclass(frozen=True)
class ConfirmationReport:
    experiment_id: str
    version: str
    prospective_cutoff: str
    family_alpha: float
    per_claim_alpha: float
    obf_constant: float
    target_power: float
    market_core_fit_sha256: str
    ledger_sha256: str
    outcomes_sha256: str
    hypotheses: tuple[HypothesisReport, ...]
    artifact_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _self_hash(payload: dict[str, object], field: str = "artifact_sha256") -> str:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return _sha256_bytes(_canonical_json(unsigned))


def _parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware ISO-8601 values")
    return parsed


def _logit(probability: float) -> float:
    if not math.isfinite(probability) or not 0.0 < probability < 1.0:
        raise ValueError("probability must be finite and in (0, 1)")
    clipped = min(max(float(probability), _LOGIT_CLIP), 1.0 - _LOGIT_CLIP)
    return math.log(clipped / (1.0 - clipped))


def _clip_probability(value: float) -> float:
    return min(max(float(value), _LOGIT_CLIP), 1.0 - _LOGIT_CLIP)


def _find_atp_profile_claim(results: dict[str, object]) -> dict[str, object]:
    adv = results.get("market_edge_adv_001")
    if not isinstance(adv, dict):
        raise ValueError("validation bundle missing market_edge_adv_001")
    family = adv.get("family_report")
    if not isinstance(family, dict):
        raise ValueError("market_edge_adv_001 missing family_report")
    claims = family.get("claims")
    if not isinstance(claims, list):
        raise ValueError("market_edge_adv_001 family missing claims")
    matches = [
        claim
        for claim in claims
        if isinstance(claim, dict)
        and claim.get("tour") == "ATP"
        and claim.get("signal_name") == "profile_gap"
    ]
    if len(matches) != 1:
        raise ValueError("expected exactly one ATP profile_gap adversarial claim")
    return matches[0]


def freeze_market_core_fit(results: dict[str, object]) -> FrozenMarketCoreFit:
    claim = _find_atp_profile_claim(results)
    primary = claim.get("primary")
    if not isinstance(primary, dict):
        raise ValueError("ATP profile_gap claim missing primary window")
    predictions = primary.get("predictions")
    if not isinstance(predictions, list) or not predictions:
        raise ValueError("ATP profile_gap primary predictions are missing")

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in predictions:
        if not isinstance(raw, dict):
            raise ValueError("prediction rows must be objects")
        match_id = str(raw.get("match_id", ""))
        year = int(raw.get("year"))
        if not match_id or match_id in seen:
            raise ValueError("historical calibration rows require unique match_id values")
        if year > 2025:
            raise ValueError("future outcomes are forbidden in the frozen baseline fit")
        seen.add(match_id)
        market = float(raw.get("market_probability_a"))
        core = float(raw.get("core_probability_a"))
        _logit(market)
        _logit(core)
        outcome = bool(raw.get("outcome_a"))
        rows.append(
            {
                "match_id": match_id,
                "year": year,
                "market_probability_a": market,
                "core_probability_a": core,
                "outcome_a": outcome,
            }
        )

    rows.sort(key=lambda item: (int(item["year"]), str(item["match_id"])))
    market_logits = np.asarray(
        [_logit(float(item["market_probability_a"])) for item in rows],
        dtype=float,
    )
    core_logits = np.asarray(
        [_logit(float(item["core_probability_a"])) for item in rows],
        dtype=float,
    )
    outcomes = np.asarray(
        [1.0 if bool(item["outcome_a"]) else 0.0 for item in rows],
        dtype=float,
    )
    design = np.column_stack(
        [np.ones(len(rows), dtype=float), market_logits, core_logits]
    )
    if int(np.linalg.matrix_rank(design)) < design.shape[1]:
        raise ValueError("frozen Market + Core design is rank deficient")

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        linear = design @ parameters
        loss = float(np.mean(np.logaddexp(0.0, linear) - outcomes * linear))
        residual = expit(linear) - outcomes
        gradient = np.mean(design * residual[:, None], axis=0)
        return loss, np.asarray(gradient, dtype=float)

    result = minimize(
        lambda parameters: objective(parameters)[0],
        np.asarray([0.0, 1.0, 0.0], dtype=float),
        jac=lambda parameters: objective(parameters)[1],
        method="BFGS",
        options={"maxiter": 1000, "gtol": 1e-8},
    )
    if (
        not result.success
        or not np.all(np.isfinite(result.x))
        or not math.isfinite(float(result.fun))
    ):
        raise RuntimeError(f"future baseline calibration failed: {result.message}")

    source_bundle_sha = str(results.get("bundle_sha256", ""))
    if not source_bundle_sha:
        raise ValueError("validation bundle missing bundle_sha256")
    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "source_bundle_sha256": source_bundle_sha,
        "source_claim": "ATP/profile_gap/MARKET-EDGE-ADV-001 primary OOS components",
        "training_rows_sha256": _sha256_bytes(_canonical_json(rows)),
        "training_n": len(rows),
        "training_start_year": min(int(item["year"]) for item in rows),
        "training_end_year": max(int(item["year"]) for item in rows),
        "intercept": float(result.x[0]),
        "market_logit_slope": float(result.x[1]),
        "core_logit_slope": float(result.x[2]),
    }
    digest = _self_hash(unsigned)
    return FrozenMarketCoreFit(**unsigned, artifact_sha256=digest)


def fit_as_dict(fit: FrozenMarketCoreFit) -> dict[str, object]:
    return asdict(fit)


def verify_fit_payload(payload: dict[str, object]) -> FrozenMarketCoreFit:
    stored = str(payload.get("artifact_sha256", ""))
    if not stored or _self_hash(payload) != stored:
        raise ValueError("frozen Market + Core fit digest mismatch")
    fit = FrozenMarketCoreFit(**payload)
    if fit.training_end_year > 2025:
        raise ValueError("frozen fit includes forbidden post-2025 training outcomes")
    return fit


def market_core_probability(
    market_probability_a: float,
    core_probability_a: float,
    fit: FrozenMarketCoreFit,
) -> float:
    linear = (
        fit.intercept
        + fit.market_logit_slope * _logit(market_probability_a)
        + fit.core_logit_slope * _logit(core_probability_a)
    )
    return float(expit(linear))


def matching_hypotheses(profile_gap: float) -> tuple[str, ...]:
    if not math.isfinite(profile_gap):
        raise ValueError("profile_gap must be finite")
    matches: list[str] = []
    for hypothesis in HYPOTHESES:
        if hypothesis.rule == "profile_gap_lt" and profile_gap < hypothesis.threshold:
            matches.append(hypothesis.hypothesis_id)
        elif (
            hypothesis.rule == "abs_profile_gap_ge"
            and abs(profile_gap) >= hypothesis.threshold
        ):
            matches.append(hypothesis.hypothesis_id)
    return tuple(matches)


def _reject_result_fields(raw: dict[str, object]) -> None:
    for key in raw:
        lowered = key.lower()
        if any(token in lowered for token in _RESULT_FIELD_TOKENS):
            raise ValueError(f"prospective input contains forbidden result field: {key}")


def build_prospective_record(
    raw: dict[str, object],
    *,
    fit: FrozenMarketCoreFit,
) -> ProspectiveRecord:
    _reject_result_fields(raw)
    match_id = str(raw.get("match_id", ""))
    tour = str(raw.get("tour", ""))
    scheduled_start = str(raw.get("scheduled_start", ""))
    observed_at = str(raw.get("observed_at", ""))
    market_source = str(raw.get("market_source", ""))
    if not match_id:
        raise ValueError("match_id must be non-empty")
    if tour != "ATP":
        raise ValueError("PATTERN-CONFIRM-001 is ATP only")
    if not market_source:
        raise ValueError("market_source must be non-empty")

    start = _parse_aware_datetime(scheduled_start)
    observed = _parse_aware_datetime(observed_at)
    cutoff = _parse_aware_datetime(_PROSPECTIVE_CUTOFF)
    if start < cutoff:
        raise ValueError("scheduled start precedes prospective confirmation cutoff")
    if observed >= start:
        raise ValueError("observation must occur before scheduled start")

    market = float(raw.get("market_probability_a"))
    core = float(raw.get("core_probability_a"))
    gap = float(raw.get("profile_gap"))
    _logit(market)
    _logit(core)
    if not math.isfinite(gap):
        raise ValueError("profile_gap must be finite")

    source_digest = _sha256_bytes(_canonical_json(raw))
    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "match_id": match_id,
        "tour": tour,
        "scheduled_start": start.isoformat(),
        "observed_at": observed.isoformat(),
        "market_source": market_source,
        "market_probability_a": market,
        "core_probability_a": core,
        "profile_gap": gap,
        "market_core_probability_a": market_core_probability(market, core, fit),
        "market_core_fit_sha256": fit.artifact_sha256,
        "matched_hypotheses": matching_hypotheses(gap),
        "source_row_sha256": source_digest,
    }
    digest = _sha256_bytes(_canonical_json(unsigned))
    return ProspectiveRecord(**unsigned, record_sha256=digest)


def prospective_record_as_dict(record: ProspectiveRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["matched_hypotheses"] = list(record.matched_hypotheses)
    return payload


def verify_prospective_record(payload: dict[str, object]) -> ProspectiveRecord:
    stored = str(payload.get("record_sha256", ""))
    unsigned = dict(payload)
    unsigned.pop("record_sha256", None)
    if not stored or _sha256_bytes(_canonical_json(unsigned)) != stored:
        raise ValueError("prospective record digest mismatch")
    normalized = dict(payload)
    normalized["matched_hypotheses"] = tuple(payload.get("matched_hypotheses", ()))
    return ProspectiveRecord(**normalized)


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("JSONL rows must be objects")
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows
        )
    )


def log_prospective_rows(
    raw_rows: list[dict[str, object]],
    *,
    fit: FrozenMarketCoreFit,
) -> list[ProspectiveRecord]:
    records = [build_prospective_record(raw, fit=fit) for raw in raw_rows]
    ids = [record.match_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("prospective input contains duplicate match_id values")
    return sorted(
        records,
        key=lambda record: (
            _parse_aware_datetime(record.scheduled_start),
            record.match_id,
        ),
    )


def load_settled_outcomes(rows: list[dict[str, object]]) -> dict[str, SettledOutcome]:
    result: dict[str, SettledOutcome] = {}
    for raw in rows:
        match_id = str(raw.get("match_id", ""))
        if not match_id or match_id in result:
            raise ValueError("settlement rows require unique non-empty match_id values")
        retirement = bool(raw.get("retirement", False))
        walkover = bool(raw.get("walkover", False))
        outcome_raw = raw.get("outcome_a")
        outcome = None if outcome_raw is None else bool(outcome_raw)
        if not retirement and not walkover and outcome is None:
            raise ValueError("settled non-excluded rows require outcome_a")
        result[match_id] = SettledOutcome(
            match_id=match_id,
            outcome_a=outcome,
            retirement=retirement,
            walkover=walkover,
        )
    return result


def _score_look(
    records: list[ProspectiveRecord],
    outcomes: dict[str, SettledOutcome],
    hypothesis: PatternHypothesis,
    *,
    look_index: int,
    look_n: int,
) -> LookResult:
    subset = records[:look_n]
    y = [bool(outcomes[row.match_id].outcome_a) for row in subset]
    baseline = [row.market_core_probability_a for row in subset]
    residual = np.asarray(
        [
            (1.0 if outcome else 0.0) - probability
            for outcome, probability in zip(y, baseline, strict=True)
        ],
        dtype=float,
    )
    mean_residual = float(np.mean(residual))
    sample_sd = float(np.std(residual, ddof=1))
    if not math.isfinite(sample_sd) or sample_sd <= 0.0:
        raise ValueError("residual sample SD must be positive")
    z = -mean_residual / (sample_sd / math.sqrt(look_n))
    corrected = [
        _clip_probability(probability + hypothesis.correction)
        for probability in baseline
    ]
    baseline_brier = brier_score(y, baseline)
    corrected_brier = brier_score(y, corrected)
    baseline_log_loss = binary_log_loss(y, baseline)
    corrected_log_loss = binary_log_loss(y, corrected)
    brier_improvement = baseline_brier - corrected_brier
    log_loss_improvement = baseline_log_loss - corrected_log_loss
    boundary = hypothesis.z_boundaries[look_index]
    efficacy = bool(z >= boundary)
    score_gate = bool(brier_improvement > 0.0 and log_loss_improvement > 0.0)
    confirmed = bool(efficacy and mean_residual < 0.0 and score_gate)
    return LookResult(
        look_index=look_index + 1,
        n=look_n,
        z=float(z),
        boundary=boundary,
        mean_residual=mean_residual,
        sample_sd=sample_sd,
        baseline_brier=baseline_brier,
        corrected_brier=corrected_brier,
        brier_improvement=brier_improvement,
        baseline_log_loss=baseline_log_loss,
        corrected_log_loss=corrected_log_loss,
        log_loss_improvement=log_loss_improvement,
        efficacy_boundary_crossed=efficacy,
        proper_score_gate=score_gate,
        confirmed_at_look=confirmed,
    )


def evaluate_hypothesis(
    records: list[ProspectiveRecord],
    outcomes: dict[str, SettledOutcome],
    hypothesis: PatternHypothesis,
) -> HypothesisReport:
    chronological = sorted(
        [
            record
            for record in records
            if hypothesis.hypothesis_id in record.matched_hypotheses
            and record.match_id in outcomes
        ],
        key=lambda record: (
            _parse_aware_datetime(record.scheduled_start),
            record.match_id,
        ),
    )
    retirement_n = sum(outcomes[row.match_id].retirement for row in chronological)
    walkover_n = sum(outcomes[row.match_id].walkover for row in chronological)
    eligible = [
        row
        for row in chronological
        if not outcomes[row.match_id].retirement
        and not outcomes[row.match_id].walkover
        and outcomes[row.match_id].outcome_a is not None
    ]

    looks: list[LookResult] = []
    confirmed_look: int | None = None
    for look_index, look_n in enumerate(hypothesis.look_ns):
        if len(eligible) < look_n:
            break
        result = _score_look(
            eligible,
            outcomes,
            hypothesis,
            look_index=look_index,
            look_n=look_n,
        )
        looks.append(result)
        if result.confirmed_at_look:
            confirmed_look = result.look_index
            break

    if confirmed_look is not None:
        status: ConfirmationStatus = "CONFIRMED"
    elif len(eligible) >= hypothesis.max_n:
        status = "FAILED_TO_CONFIRM"
    else:
        status = "ACCUMULATING"

    return HypothesisReport(
        hypothesis_id=hypothesis.hypothesis_id,
        source_candidate_id=hypothesis.source_candidate_id,
        available_qualifying_n=len(eligible),
        excluded_retirement_n=retirement_n,
        excluded_walkover_n=walkover_n,
        status=status,
        confirmed_look=confirmed_look,
        completed_looks=tuple(looks),
    )


def evaluate_family(
    records: list[ProspectiveRecord],
    outcomes: dict[str, SettledOutcome],
    *,
    fit: FrozenMarketCoreFit,
    ledger_sha256: str,
    outcomes_sha256: str,
) -> ConfirmationReport:
    if any(record.market_core_fit_sha256 != fit.artifact_sha256 for record in records):
        raise ValueError("prospective ledger mixes frozen Market + Core fit versions")
    reports = tuple(
        evaluate_hypothesis(records, outcomes, hypothesis) for hypothesis in HYPOTHESES
    )
    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "prospective_cutoff": _PROSPECTIVE_CUTOFF,
        "family_alpha": _FAMILY_ALPHA,
        "per_claim_alpha": _CLAIM_ALPHA,
        "obf_constant": _OBF_CONSTANT,
        "target_power": _TARGET_POWER,
        "market_core_fit_sha256": fit.artifact_sha256,
        "ledger_sha256": ledger_sha256,
        "outcomes_sha256": outcomes_sha256,
        "hypotheses": [asdict(report) for report in reports],
    }
    digest = _self_hash(unsigned)
    return ConfirmationReport(
        experiment_id=_EXPERIMENT_ID,
        version=_VERSION,
        prospective_cutoff=_PROSPECTIVE_CUTOFF,
        family_alpha=_FAMILY_ALPHA,
        per_claim_alpha=_CLAIM_ALPHA,
        obf_constant=_OBF_CONSTANT,
        target_power=_TARGET_POWER,
        market_core_fit_sha256=fit.artifact_sha256,
        ledger_sha256=ledger_sha256,
        outcomes_sha256=outcomes_sha256,
        hypotheses=reports,
        artifact_sha256=digest,
    )


def report_as_dict(report: ConfirmationReport) -> dict[str, object]:
    return asdict(report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PATTERN-CONFIRM-001 utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze-fit")
    freeze.add_argument("--results", required=True, type=Path)
    freeze.add_argument("--output", required=True, type=Path)

    log = sub.add_parser("log")
    log.add_argument("--fit", required=True, type=Path)
    log.add_argument("--input", required=True, type=Path)
    log.add_argument("--output", required=True, type=Path)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--fit", required=True, type=Path)
    evaluate.add_argument("--ledger", required=True, type=Path)
    evaluate.add_argument("--outcomes", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "freeze-fit":
        payload = json.loads(args.results.read_text())
        if not isinstance(payload, dict):
            raise ValueError("validation results must be a JSON object")
        fit = freeze_market_core_fit(payload)
        args.output.write_text(
            json.dumps(fit_as_dict(fit), indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        )
        return

    fit_payload = json.loads(args.fit.read_text())
    if not isinstance(fit_payload, dict):
        raise ValueError("frozen fit must be a JSON object")
    fit = verify_fit_payload(fit_payload)

    if args.command == "log":
        raw_rows = _load_jsonl(args.input)
        records = log_prospective_rows(raw_rows, fit=fit)
        _write_jsonl(
            args.output,
            [prospective_record_as_dict(record) for record in records],
        )
        return

    if args.command == "evaluate":
        ledger_rows = _load_jsonl(args.ledger)
        records = [verify_prospective_record(row) for row in ledger_rows]
        ids = [record.match_id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("prospective ledger contains duplicate match_id values")
        outcome_rows = _load_jsonl(args.outcomes)
        outcomes = load_settled_outcomes(outcome_rows)
        report = evaluate_family(
            records,
            outcomes,
            fit=fit,
            ledger_sha256=_sha256_file(args.ledger),
            outcomes_sha256=_sha256_file(args.outcomes),
        )
        args.output.write_text(
            json.dumps(report_as_dict(report), indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        )
        return

    raise RuntimeError("unreachable command")


if __name__ == "__main__":
    main()
