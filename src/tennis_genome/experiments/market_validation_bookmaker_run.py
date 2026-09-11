from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from tennis_genome.experiments.market_book_gate import load_confirmatory_market_book_qa
from tennis_genome.experiments.market_edge_adv_bookmaker_pipeline import (
    build_bookmaker_market_edge_adversarial_artifact,
)
from tennis_genome.experiments.market_edge_bookmaker_pipeline import (
    build_bookmaker_market_edge_artifact,
)
from tennis_genome.market.bookmaker_manifest import load_bookmaker_source_manifest

_EXPERIMENT_ID = "MARKET-VALIDATION-BOOK-RUN-001"
_STAGE_A = "OUTCOME_LOCKED_COMPLETE"
_RECENT_YEARS = (2021, 2022, 2023, 2024, 2025)
_CLAIMS = (
    ("ATP", "profile_gap"),
    ("WTA", "profile_gap"),
    ("ATP", "genome"),
    ("WTA", "genome"),
)
_POWER_FAMILY_ALPHA = 0.05
_POWER_FAMILY_SIZE = 4
_POWER_PLANNING_ALPHA = 0.0125
_POWER_MIN_PRIOR_ROWS = 1000


@dataclass(frozen=True)
class BookmakerPowerClaimSeal:
    tour: str
    signal_name: str
    identifiable_evaluation_years: tuple[int, ...]


@dataclass(frozen=True)
class BookmakerOutcomeUnlockSeal:
    experiment_id: str
    stage: str
    winner_outcomes_permitted_for_stage_b: bool
    market_policy: str
    sealed_file_sha256: dict[str, str]
    qa_artifact_sha256: str
    qa_overall_status: str
    qa_tour_status: dict[str, str]
    qa_outcomes_sha256: str
    power_mde_artifact_sha256: str
    power_claims: tuple[BookmakerPowerClaimSeal, ...]
    seal_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BookmakerValidationResultBundle:
    experiment_id: str
    stage: str
    outcome_open: bool
    stage_a_seal_sha256: str
    sealed_file_sha256: dict[str, str]
    outcomes_sha256: str
    market_edge_001_sha256: str
    market_edge_adv_001_sha256: str
    market_edge_001: dict[str, object]
    market_edge_adv_001: dict[str, object]
    bundle_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


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


def _payload_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _valid_sha256(value: object, *, label: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return text


def _load_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _verify_self_digest(payload: dict[str, Any], *, label: str) -> str:
    digest = _valid_sha256(payload.get("artifact_sha256"), label=f"{label}.artifact_sha256")
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    expected = _payload_sha256(unsigned)
    if digest != expected:
        raise ValueError(f"{label} artifact_sha256 mismatch")
    return expected


def _verify_artifact_input_hashes(
    payload: dict[str, Any],
    *,
    actual: dict[str, str],
    required_names: tuple[str, ...],
    label: str,
) -> dict[str, str]:
    stored = payload.get("input_sha256")
    if not isinstance(stored, dict):
        raise ValueError(f"{label} lacks input_sha256")
    normalized = {
        str(name): _valid_sha256(value, label=f"{label}.input_sha256.{name}")
        for name, value in stored.items()
    }
    for name in required_names:
        if normalized.get(name) != actual[name]:
            raise ValueError(f"{label} input hash mismatch for {name}")
    return normalized


def _power_claims(power: dict[str, Any]) -> tuple[BookmakerPowerClaimSeal, ...]:
    if power.get("experiment_id") != "POWER-MDE-001":
        raise ValueError("unexpected POWER-MDE experiment ID")
    if power.get("outcome_blind") is not True:
        raise ValueError("POWER-MDE artifact must declare outcome_blind=true")
    if power.get("family_size") != _POWER_FAMILY_SIZE:
        raise ValueError("POWER-MDE family_size differs from frozen design")
    if power.get("family_alpha") != _POWER_FAMILY_ALPHA:
        raise ValueError("POWER-MDE family_alpha differs from frozen design")
    if power.get("conservative_planning_alpha") != _POWER_PLANNING_ALPHA:
        raise ValueError("POWER-MDE planning alpha differs from frozen design")

    claims = power.get("claims")
    if not isinstance(claims, list) or len(claims) != len(_CLAIMS):
        raise ValueError("POWER-MDE artifact must contain exactly four claims")
    seen: set[tuple[str, str]] = set()
    result: list[BookmakerPowerClaimSeal] = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("POWER-MDE contains an invalid claim row")
        key = (str(claim.get("tour", "")), str(claim.get("signal_name", "")))
        if key not in _CLAIMS or key in seen:
            raise ValueError("POWER-MDE claims are missing, duplicated, or unexpected")
        seen.add(key)
        if claim.get("min_prior_rows") != _POWER_MIN_PRIOR_ROWS:
            raise ValueError("POWER-MDE min_prior_rows differs from frozen design")
        if claim.get("family_size") != _POWER_FAMILY_SIZE:
            raise ValueError("POWER-MDE claim family_size differs from frozen design")
        if claim.get("family_alpha") != _POWER_FAMILY_ALPHA:
            raise ValueError("POWER-MDE claim family_alpha differs from frozen design")
        if claim.get("conservative_planning_alpha") != _POWER_PLANNING_ALPHA:
            raise ValueError("POWER-MDE claim planning alpha differs from frozen design")
        plans = claim.get("year_plans")
        if not isinstance(plans, list):
            raise ValueError(f"POWER-MDE {key} lacks year_plans")
        identifiable = {
            int(plan.get("evaluation_year", 0))
            for plan in plans
            if isinstance(plan, dict) and plan.get("identifiable") is True
        }
        missing_recent = [year for year in _RECENT_YEARS if year not in identifiable]
        if missing_recent:
            raise ValueError(f"POWER-MDE {key} lacks identifiable years {missing_recent}")
        result.append(
            BookmakerPowerClaimSeal(
                tour=key[0],
                signal_name=key[1],
                identifiable_evaluation_years=tuple(sorted(identifiable)),
            )
        )
    if seen != set(_CLAIMS):
        raise ValueError("POWER-MDE four-claim family is incomplete")
    return tuple(sorted(result, key=lambda row: (row.tour, row.signal_name)))


def _sealed_paths(
    *,
    source_manifest: str | Path,
    market_book_records: str | Path,
    pre_match: str | Path,
    market_book_qa: str | Path,
    power_mde: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
) -> dict[str, Path]:
    return {
        "source_manifest": Path(source_manifest),
        "market_book_records": Path(market_book_records),
        "pre_match": Path(pre_match),
        "market_book_qa": Path(market_book_qa),
        "power_mde": Path(power_mde),
        "profile_gap_atp": Path(profile_gap_atp),
        "profile_gap_wta": Path(profile_gap_wta),
        "genome_atp": Path(genome_atp),
        "genome_wta": Path(genome_wta),
    }


def create_bookmaker_outcome_unlock_seal(
    *,
    source_manifest: str | Path,
    market_book_records: str | Path,
    pre_match: str | Path,
    market_book_qa: str | Path,
    power_mde: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
) -> BookmakerOutcomeUnlockSeal:
    paths = _sealed_paths(
        source_manifest=source_manifest,
        market_book_records=market_book_records,
        pre_match=pre_match,
        market_book_qa=market_book_qa,
        power_mde=power_mde,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
    )
    hashes = {name: _sha256_file(path) for name, path in sorted(paths.items())}

    manifest = load_bookmaker_source_manifest(paths["source_manifest"])
    if manifest.market_policy != "BOOKMAKER_CLOSE_V1":
        raise ValueError("bookmaker source manifest market policy differs from frozen design")

    qa = _load_json_object(paths["market_book_qa"], label="MARKET-BOOK-QA artifact")
    qa_digest = _verify_self_digest(qa, label="MARKET-BOOK-QA artifact")
    qa_status = load_confirmatory_market_book_qa(paths["market_book_qa"])
    qa_hashes = _verify_artifact_input_hashes(
        qa,
        actual=hashes,
        required_names=("source_manifest", "market_book_records", "pre_match"),
        label="MARKET-BOOK-QA artifact",
    )
    qa_outcomes_sha = qa_hashes.get("outcomes")
    if qa_outcomes_sha is None:
        raise ValueError("MARKET-BOOK-QA artifact lacks outcomes input hash")

    power = _load_json_object(paths["power_mde"], label="POWER-MDE artifact")
    power_digest = _verify_self_digest(power, label="POWER-MDE artifact")
    _verify_artifact_input_hashes(
        power,
        actual=hashes,
        required_names=(
            "market_book_qa",
            "market_book_records",
            "pre_match",
            "profile_gap_atp",
            "profile_gap_wta",
            "genome_atp",
            "genome_wta",
        ),
        label="POWER-MDE artifact",
    )
    claims = _power_claims(power)

    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "stage": _STAGE_A,
        "winner_outcomes_permitted_for_stage_b": True,
        "market_policy": "BOOKMAKER_CLOSE_V1",
        "sealed_file_sha256": dict(sorted(hashes.items())),
        "qa_artifact_sha256": qa_digest,
        "qa_overall_status": str(qa.get("overall_status", "")),
        "qa_tour_status": dict(sorted(qa_status.items())),
        "qa_outcomes_sha256": qa_outcomes_sha,
        "power_mde_artifact_sha256": power_digest,
        "power_claims": [asdict(row) for row in claims],
    }
    seal_hash = _payload_sha256(unsigned)
    return BookmakerOutcomeUnlockSeal(
        experiment_id=_EXPERIMENT_ID,
        stage=_STAGE_A,
        winner_outcomes_permitted_for_stage_b=True,
        market_policy="BOOKMAKER_CLOSE_V1",
        sealed_file_sha256=dict(sorted(hashes.items())),
        qa_artifact_sha256=qa_digest,
        qa_overall_status=str(qa.get("overall_status", "")),
        qa_tour_status=dict(sorted(qa_status.items())),
        qa_outcomes_sha256=qa_outcomes_sha,
        power_mde_artifact_sha256=power_digest,
        power_claims=claims,
        seal_sha256=seal_hash,
    )


def _verify_seal(payload: dict[str, Any]) -> str:
    if payload.get("experiment_id") != _EXPERIMENT_ID:
        raise ValueError("unexpected bookmaker validation seal experiment ID")
    if payload.get("stage") != _STAGE_A:
        raise ValueError("bookmaker validation seal is not outcome-unlocked")
    if payload.get("winner_outcomes_permitted_for_stage_b") is not True:
        raise ValueError("bookmaker validation seal does not permit Stage B")
    if payload.get("market_policy") != "BOOKMAKER_CLOSE_V1":
        raise ValueError("bookmaker validation seal market policy mismatch")
    _valid_sha256(payload.get("qa_outcomes_sha256"), label="seal.qa_outcomes_sha256")
    digest = _valid_sha256(payload.get("seal_sha256"), label="seal.seal_sha256")
    unsigned = dict(payload)
    unsigned.pop("seal_sha256", None)
    expected = _payload_sha256(unsigned)
    if digest != expected:
        raise ValueError("bookmaker validation seal digest mismatch")
    return expected


def _verify_stage_b_inputs(
    *,
    seal_path: str | Path,
    paths: dict[str, Path],
) -> tuple[dict[str, Any], str]:
    seal = _load_json_object(seal_path, label="bookmaker validation seal")
    seal_digest = _verify_seal(seal)
    stored = seal.get("sealed_file_sha256")
    if not isinstance(stored, dict) or set(stored) != set(paths):
        raise ValueError("bookmaker validation sealed file set does not match Stage B")
    for name, path in sorted(paths.items()):
        if str(stored.get(name, "")).lower() != _sha256_file(path):
            raise ValueError(f"sealed Stage A file changed before Stage B: {name}")

    load_bookmaker_source_manifest(paths["source_manifest"])
    qa = _load_json_object(paths["market_book_qa"], label="MARKET-BOOK-QA artifact")
    qa_digest = _verify_self_digest(qa, label="MARKET-BOOK-QA artifact")
    if qa_digest != seal.get("qa_artifact_sha256"):
        raise ValueError("MARKET-BOOK-QA artifact differs from Stage A seal")
    load_confirmatory_market_book_qa(paths["market_book_qa"])

    power = _load_json_object(paths["power_mde"], label="POWER-MDE artifact")
    power_digest = _verify_self_digest(power, label="POWER-MDE artifact")
    if power_digest != seal.get("power_mde_artifact_sha256"):
        raise ValueError("POWER-MDE artifact differs from Stage A seal")
    _power_claims(power)
    return seal, seal_digest


def run_bookmaker_outcome_open_stage(
    *,
    seal_path: str | Path,
    source_manifest: str | Path,
    market_book_records: str | Path,
    pre_match: str | Path,
    market_book_qa: str | Path,
    power_mde: str | Path,
    outcomes: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    min_prior_rows: int = _POWER_MIN_PRIOR_ROWS,
) -> BookmakerValidationResultBundle:
    if min_prior_rows != _POWER_MIN_PRIOR_ROWS:
        raise ValueError("bookmaker validation min_prior_rows is frozen at 1000")
    paths = _sealed_paths(
        source_manifest=source_manifest,
        market_book_records=market_book_records,
        pre_match=pre_match,
        market_book_qa=market_book_qa,
        power_mde=power_mde,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
    )
    seal, seal_digest = _verify_stage_b_inputs(seal_path=seal_path, paths=paths)

    outcomes_hash = _sha256_file(outcomes)
    if outcomes_hash != seal.get("qa_outcomes_sha256"):
        raise ValueError("outcomes file differs from the file frozen by MARKET-BOOK-QA")

    edge = build_bookmaker_market_edge_artifact(
        market_book_qa=market_book_qa,
        market_book_records=market_book_records,
        pre_match=pre_match,
        outcomes_path=outcomes,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
        min_prior_rows=_POWER_MIN_PRIOR_ROWS,
    )
    edge_adv = build_bookmaker_market_edge_adversarial_artifact(
        market_book_qa=market_book_qa,
        market_book_records=market_book_records,
        pre_match=pre_match,
        outcomes_path=outcomes,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
        min_prior_rows=_POWER_MIN_PRIOR_ROWS,
    )
    edge_dict = edge.to_dict()
    edge_adv_dict = edge_adv.to_dict()
    edge_hash = _payload_sha256(edge_dict)
    edge_adv_hash = _payload_sha256(edge_adv_dict)
    sealed_hashes = cast(dict[str, str], seal["sealed_file_sha256"])
    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "stage": "OUTCOME_OPEN_COMPLETE",
        "outcome_open": True,
        "stage_a_seal_sha256": seal_digest,
        "sealed_file_sha256": dict(sorted(sealed_hashes.items())),
        "outcomes_sha256": outcomes_hash,
        "market_edge_001_sha256": edge_hash,
        "market_edge_adv_001_sha256": edge_adv_hash,
        "market_edge_001": edge_dict,
        "market_edge_adv_001": edge_adv_dict,
    }
    bundle_hash = _payload_sha256(unsigned)
    return BookmakerValidationResultBundle(
        experiment_id=_EXPERIMENT_ID,
        stage="OUTCOME_OPEN_COMPLETE",
        outcome_open=True,
        stage_a_seal_sha256=seal_digest,
        sealed_file_sha256=dict(sorted(sealed_hashes.items())),
        outcomes_sha256=outcomes_hash,
        market_edge_001_sha256=edge_hash,
        market_edge_adv_001_sha256=edge_adv_hash,
        market_edge_001=edge_dict,
        market_edge_adv_001=edge_adv_dict,
        bundle_sha256=bundle_hash,
    )


def _write_json(value: object, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _add_shared(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--market-book-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--market-book-qa", required=True, type=Path)
    parser.add_argument("--power-mde", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run staged bookmaker market validation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seal = subparsers.add_parser("seal", help="verify locked gates and create Stage-A seal")
    _add_shared(seal)
    seal.add_argument("--output", required=True, type=Path)
    run = subparsers.add_parser("run", help="verify seal, then open outcomes and score")
    _add_shared(run)
    run.add_argument("--seal", required=True, type=Path)
    run.add_argument("--outcomes", required=True, type=Path)
    run.add_argument("--min-prior-rows", type=int, default=_POWER_MIN_PRIOR_ROWS)
    run.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    shared = dict(
        source_manifest=args.source_manifest,
        market_book_records=args.market_book_records,
        pre_match=args.pre_match,
        market_book_qa=args.market_book_qa,
        power_mde=args.power_mde,
        profile_gap_atp=args.profile_gap_atp,
        profile_gap_wta=args.profile_gap_wta,
        genome_atp=args.genome_atp,
        genome_wta=args.genome_wta,
    )
    if args.command == "seal":
        result = create_bookmaker_outcome_unlock_seal(**shared)
    else:
        result = run_bookmaker_outcome_open_stage(
            seal_path=args.seal,
            outcomes=args.outcomes,
            min_prior_rows=args.min_prior_rows,
            **shared,
        )
    _write_json(result.to_dict(), args.output)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
