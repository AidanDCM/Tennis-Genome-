from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tennis_genome.experiments.market_edge_adv_pipeline import (
    build_market_edge_adversarial_artifact,
)
from tennis_genome.experiments.market_edge_pipeline import build_market_edge_artifact
from tennis_genome.market.historical_manifest import load_historical_source_manifest

_EXPERIMENT_ID = "MARKET-VALIDATION-RUNNER-v1"
_SEAL_VERSION = "market-validation-preoutcome-seal-v1"
_CONFIRMATORY_QA_STATUS = "ELIGIBLE_CONFIRMATORY"
_REQUIRED_TOURS = {"ATP", "WTA"}
_REQUIRED_QA_GATES = {
    "overall_close_coverage_at_least_60pct",
    "every_recent_year_close_coverage_at_least_50pct",
    "every_recent_year_at_least_100_rows",
    "at_least_1000_prior_rows_before_first_evaluation_year",
    "at_least_five_evaluation_years",
    "all_2021_2025_years_in_evaluation_population",
    "passed",
}
_REQUIRED_POWER_CLAIMS = {
    ("ATP", "profile_gap"),
    ("WTA", "profile_gap"),
    ("ATP", "genome"),
    ("WTA", "genome"),
}
_POWER_FAMILY_ALPHA = 0.05
_POWER_FAMILY_SIZE = 4
_POWER_PLANNING_ALPHA = 0.0125
_POWER_MIN_PRIOR_ROWS = 1000


@dataclass(frozen=True)
class PreOutcomeSeal:
    experiment_id: str
    seal_version: str
    created_at: str
    source_bundle_sha256: str
    source_manifest_sha256: str
    market_hist_records_sha256: str
    market_hist_qa_sha256: str
    power_mde_sha256: str
    pre_match_sha256: str
    profile_gap_atp_sha256: str
    profile_gap_wta_sha256: str
    genome_atp_sha256: str
    genome_wta_sha256: str
    qa_outcomes_sha256: str
    qa_tour_status: dict[str, str]
    power_outcome_blind: bool
    artifact_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ConfirmatoryExecutionLedger:
    experiment_id: str
    created_at: str
    preoutcome_seal_sha256: str
    outcomes_sha256: str
    market_edge_output_sha256: str
    market_edge_adv_output_sha256: str
    market_edge_internal_artifact_sha256: str | None
    market_edge_adv_internal_artifact_sha256: str | None
    artifact_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _artifact_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _load_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _valid_sha256(value: object, *, label: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return text


def _verify_embedded_artifact_hash(payload: dict[str, Any], *, label: str) -> str:
    provided = _valid_sha256(payload.get("artifact_sha256"), label=f"{label}.artifact_sha256")
    scientific = {key: value for key, value in payload.items() if key != "artifact_sha256"}
    expected = _artifact_hash(scientific)
    if provided != expected:
        raise ValueError(f"{label} artifact SHA-256 mismatch")
    return provided


def _utc_timestamp(value: datetime | None) -> str:
    instant = value or datetime.now(UTC)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    return instant.astimezone(UTC).isoformat()


def _qa_status(payload: dict[str, Any]) -> dict[str, str]:
    if payload.get("experiment_id") != "MARKET-HIST-QA-001":
        raise ValueError("unexpected MARKET-HIST-QA experiment ID")
    if payload.get("effective_overall_status") != _CONFIRMATORY_QA_STATUS:
        raise ValueError("MARKET-HIST-QA effective status is not confirmatory")
    report = payload.get("qa_report")
    if not isinstance(report, dict):
        raise ValueError("MARKET-HIST-QA artifact lacks qa_report")
    if report.get("overall_status") != _CONFIRMATORY_QA_STATUS:
        raise ValueError("MARKET-HIST-QA report status is not confirmatory")
    tours = report.get("tours")
    if not isinstance(tours, list):
        raise ValueError("MARKET-HIST-QA qa_report.tours must be a list")
    result: dict[str, str] = {}
    for item in tours:
        if not isinstance(item, dict):
            raise ValueError("invalid MARKET-HIST-QA tour row")
        tour = str(item.get("tour", ""))
        if tour not in _REQUIRED_TOURS:
            raise ValueError(f"invalid MARKET-HIST-QA tour: {tour!r}")
        if tour in result:
            raise ValueError(f"duplicate MARKET-HIST-QA tour: {tour}")
        status = str(item.get("status", ""))
        gates = item.get("gates")
        if not isinstance(gates, dict):
            raise ValueError(f"MARKET-HIST-QA {tour} row lacks coverage gates")
        if set(gates) != _REQUIRED_QA_GATES:
            raise ValueError(f"MARKET-HIST-QA {tour} gate set differs from frozen design")
        if any(gates[key] is not True for key in _REQUIRED_QA_GATES):
            raise ValueError(f"MARKET-HIST-QA {tour} has a failed frozen coverage gate")
        result[tour] = status
    if set(result) != _REQUIRED_TOURS:
        raise ValueError("MARKET-HIST-QA must report ATP and WTA")
    blocked = sorted(
        tour for tour, status in result.items() if status != _CONFIRMATORY_QA_STATUS
    )
    if blocked:
        raise ValueError(
            "confirmatory validation runner requires QA-eligible ATP and WTA; "
            f"blocked={blocked}"
        )
    return dict(sorted(result.items()))


def _require_hashes(
    mapping: object,
    *,
    expected: dict[str, str],
    label: str,
) -> dict[str, str]:
    if not isinstance(mapping, dict):
        raise ValueError(f"{label} input_sha256 must be an object")
    normalized = {
        str(key): _valid_sha256(value, label=f"{label}.{key}")
        for key, value in mapping.items()
    }
    for key, digest in expected.items():
        if normalized.get(key) != digest:
            raise ValueError(f"{label} input hash mismatch for {key}")
    return normalized


def _validate_power_family(payload: dict[str, Any]) -> None:
    if payload.get("family_size") != _POWER_FAMILY_SIZE:
        raise ValueError("POWER-MDE family_size differs from frozen design")
    if payload.get("family_alpha") != _POWER_FAMILY_ALPHA:
        raise ValueError("POWER-MDE family_alpha differs from frozen design")
    if payload.get("conservative_planning_alpha") != _POWER_PLANNING_ALPHA:
        raise ValueError("POWER-MDE planning alpha differs from frozen design")
    claims = payload.get("claims")
    if not isinstance(claims, list) or len(claims) != _POWER_FAMILY_SIZE:
        raise ValueError("POWER-MDE must contain exactly four claims")
    observed: set[tuple[str, str]] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("invalid POWER-MDE claim row")
        if claim.get("experiment_id") != "POWER-MDE-001":
            raise ValueError("unexpected POWER-MDE claim experiment ID")
        key = (str(claim.get("tour", "")), str(claim.get("signal_name", "")))
        if key in observed:
            raise ValueError("POWER-MDE contains a duplicate claim")
        observed.add(key)
        if claim.get("min_prior_rows") != _POWER_MIN_PRIOR_ROWS:
            raise ValueError("POWER-MDE min_prior_rows differs from frozen design")
        if claim.get("family_size") != _POWER_FAMILY_SIZE:
            raise ValueError("POWER-MDE claim family_size differs from frozen design")
        if claim.get("family_alpha") != _POWER_FAMILY_ALPHA:
            raise ValueError("POWER-MDE claim family_alpha differs from frozen design")
        if claim.get("conservative_planning_alpha") != _POWER_PLANNING_ALPHA:
            raise ValueError("POWER-MDE claim planning alpha differs from frozen design")
    if observed != _REQUIRED_POWER_CLAIMS:
        raise ValueError("POWER-MDE claim family differs from frozen four-claim design")


def build_preoutcome_seal(
    *,
    source_manifest: str | Path,
    market_hist_records: str | Path,
    market_hist_qa: str | Path,
    power_mde: str | Path,
    pre_match: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    created_at: datetime | None = None,
) -> PreOutcomeSeal:
    paths = {
        "source_manifest": Path(source_manifest),
        "market_hist_records": Path(market_hist_records),
        "market_hist_qa": Path(market_hist_qa),
        "power_mde": Path(power_mde),
        "pre_match": Path(pre_match),
        "profile_gap_atp": Path(profile_gap_atp),
        "profile_gap_wta": Path(profile_gap_wta),
        "genome_atp": Path(genome_atp),
        "genome_wta": Path(genome_wta),
    }
    file_hashes = {name: _sha256_file(path) for name, path in paths.items()}

    manifest = load_historical_source_manifest(paths["source_manifest"])
    source_bundle_sha = manifest.bundle_sha256

    qa = _load_json_object(paths["market_hist_qa"], label="MARKET-HIST-QA")
    _verify_embedded_artifact_hash(qa, label="MARKET-HIST-QA")
    tour_status = _qa_status(qa)
    qa_hashes = _require_hashes(
        qa.get("input_sha256"),
        expected={
            "source_manifest": file_hashes["source_manifest"],
            "market_hist_records": file_hashes["market_hist_records"],
            "pre_match": file_hashes["pre_match"],
        },
        label="MARKET-HIST-QA",
    )
    qa_outcomes_sha = qa_hashes.get("outcomes")
    if qa_outcomes_sha is None:
        raise ValueError("MARKET-HIST-QA must record the QA outcomes SHA-256")

    power = _load_json_object(paths["power_mde"], label="POWER-MDE")
    _verify_embedded_artifact_hash(power, label="POWER-MDE")
    if power.get("experiment_id") != "POWER-MDE-001":
        raise ValueError("unexpected POWER-MDE experiment ID")
    if power.get("outcome_blind") is not True:
        raise ValueError("POWER-MDE artifact must be explicitly outcome-blind")
    _validate_power_family(power)
    _require_hashes(
        power.get("input_sha256"),
        expected={
            "market_hist_records": file_hashes["market_hist_records"],
            "pre_match": file_hashes["pre_match"],
            "profile_gap_atp": file_hashes["profile_gap_atp"],
            "profile_gap_wta": file_hashes["profile_gap_wta"],
            "genome_atp": file_hashes["genome_atp"],
            "genome_wta": file_hashes["genome_wta"],
        },
        label="POWER-MDE",
    )

    scientific_payload: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "seal_version": _SEAL_VERSION,
        "source_bundle_sha256": source_bundle_sha,
        "source_manifest_sha256": file_hashes["source_manifest"],
        "market_hist_records_sha256": file_hashes["market_hist_records"],
        "market_hist_qa_sha256": file_hashes["market_hist_qa"],
        "power_mde_sha256": file_hashes["power_mde"],
        "pre_match_sha256": file_hashes["pre_match"],
        "profile_gap_atp_sha256": file_hashes["profile_gap_atp"],
        "profile_gap_wta_sha256": file_hashes["profile_gap_wta"],
        "genome_atp_sha256": file_hashes["genome_atp"],
        "genome_wta_sha256": file_hashes["genome_wta"],
        "qa_outcomes_sha256": qa_outcomes_sha,
        "qa_tour_status": tour_status,
        "power_outcome_blind": True,
    }
    return PreOutcomeSeal(
        **scientific_payload,
        created_at=_utc_timestamp(created_at),
        artifact_sha256=_artifact_hash(scientific_payload),
    )


def _load_preoutcome_seal(path: str | Path) -> PreOutcomeSeal:
    payload = _load_json_object(path, label="pre-outcome seal")
    if payload.get("experiment_id") != _EXPERIMENT_ID:
        raise ValueError("unexpected pre-outcome seal experiment ID")
    if payload.get("seal_version") != _SEAL_VERSION:
        raise ValueError("unexpected pre-outcome seal version")
    scientific = {
        key: value
        for key, value in payload.items()
        if key not in {"created_at", "artifact_sha256"}
    }
    expected = _artifact_hash(scientific)
    provided = _valid_sha256(payload.get("artifact_sha256"), label="seal artifact_sha256")
    if provided != expected:
        raise ValueError("pre-outcome seal artifact SHA-256 mismatch")
    return PreOutcomeSeal(**payload)


def _verify_non_outcome_inputs(
    seal: PreOutcomeSeal,
    *,
    source_manifest: str | Path,
    market_hist_records: str | Path,
    market_hist_qa: str | Path,
    power_mde: str | Path,
    pre_match: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
) -> None:
    expected = {
        "source_manifest_sha256": source_manifest,
        "market_hist_records_sha256": market_hist_records,
        "market_hist_qa_sha256": market_hist_qa,
        "power_mde_sha256": power_mde,
        "pre_match_sha256": pre_match,
        "profile_gap_atp_sha256": profile_gap_atp,
        "profile_gap_wta_sha256": profile_gap_wta,
        "genome_atp_sha256": genome_atp,
        "genome_wta_sha256": genome_wta,
    }
    for field, path in expected.items():
        if _sha256_file(path) != getattr(seal, field):
            raise ValueError(f"sealed input changed after pre-outcome freeze: {field}")


def run_confirmatory_validation(
    *,
    preoutcome_seal: str | Path,
    source_manifest: str | Path,
    market_hist_records: str | Path,
    market_hist_qa: str | Path,
    power_mde: str | Path,
    pre_match: str | Path,
    outcomes: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    output_dir: str | Path,
    created_at: datetime | None = None,
) -> ConfirmatoryExecutionLedger:
    seal = _load_preoutcome_seal(preoutcome_seal)
    _verify_non_outcome_inputs(
        seal,
        source_manifest=source_manifest,
        market_hist_records=market_hist_records,
        market_hist_qa=market_hist_qa,
        power_mde=power_mde,
        pre_match=pre_match,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
    )

    # This is the first point in the confirmatory runner where the settled-outcome
    # file is opened. Its hash must equal the file used by the already-frozen QA.
    outcomes_sha = _sha256_file(outcomes)
    if outcomes_sha != seal.qa_outcomes_sha256:
        raise ValueError("outcomes file differs from the file frozen by MARKET-HIST-QA")

    edge = build_market_edge_artifact(
        market_hist_records=market_hist_records,
        pre_match=pre_match,
        outcomes_path=outcomes,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
    )
    edge_adv = build_market_edge_adversarial_artifact(
        market_hist_qa=market_hist_qa,
        market_hist_records=market_hist_records,
        pre_match=pre_match,
        outcomes_path=outcomes,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
    )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    edge_path = destination / "market_edge_001.json"
    edge_adv_path = destination / "market_edge_adv_001.json"
    edge_bytes = json.dumps(edge.to_dict(), indent=2, sort_keys=True).encode("utf-8") + b"\n"
    adv_bytes = json.dumps(edge_adv.to_dict(), indent=2, sort_keys=True).encode("utf-8") + b"\n"
    edge_path.write_bytes(edge_bytes)
    edge_adv_path.write_bytes(adv_bytes)

    scientific_payload: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "preoutcome_seal_sha256": seal.artifact_sha256,
        "outcomes_sha256": outcomes_sha,
        "market_edge_output_sha256": hashlib.sha256(edge_bytes).hexdigest(),
        "market_edge_adv_output_sha256": hashlib.sha256(adv_bytes).hexdigest(),
        "market_edge_internal_artifact_sha256": getattr(edge, "artifact_sha256", None),
        "market_edge_adv_internal_artifact_sha256": getattr(
            edge_adv, "artifact_sha256", None
        ),
    }
    ledger = ConfirmatoryExecutionLedger(
        **scientific_payload,
        created_at=_utc_timestamp(created_at),
        artifact_sha256=_artifact_hash(scientific_payload),
    )
    ledger_path = destination / "market_validation_execution_ledger.json"
    ledger_path.write_text(
        json.dumps(ledger.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ledger


def _add_common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--market-hist-records", required=True, type=Path)
    parser.add_argument("--market-hist-qa", required=True, type=Path)
    parser.add_argument("--power-mde", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enforce the frozen licensed-market validation execution order"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    seal_parser = subparsers.add_parser("seal")
    _add_common_inputs(seal_parser)
    seal_parser.add_argument("--output", required=True, type=Path)

    evaluate_parser = subparsers.add_parser("evaluate")
    _add_common_inputs(evaluate_parser)
    evaluate_parser.add_argument("--preoutcome-seal", required=True, type=Path)
    evaluate_parser.add_argument("--outcomes", required=True, type=Path)
    evaluate_parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "seal":
        seal = build_preoutcome_seal(
            source_manifest=args.source_manifest,
            market_hist_records=args.market_hist_records,
            market_hist_qa=args.market_hist_qa,
            power_mde=args.power_mde,
            pre_match=args.pre_match,
            profile_gap_atp=args.profile_gap_atp,
            profile_gap_wta=args.profile_gap_wta,
            genome_atp=args.genome_atp,
            genome_wta=args.genome_wta,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(seal.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(seal.to_dict(), indent=2, sort_keys=True))
        return

    ledger = run_confirmatory_validation(
        preoutcome_seal=args.preoutcome_seal,
        source_manifest=args.source_manifest,
        market_hist_records=args.market_hist_records,
        market_hist_qa=args.market_hist_qa,
        power_mde=args.power_mde,
        pre_match=args.pre_match,
        outcomes=args.outcomes,
        profile_gap_atp=args.profile_gap_atp,
        profile_gap_wta=args.profile_gap_wta,
        genome_atp=args.genome_atp,
        genome_wta=args.genome_wta,
        output_dir=args.output_dir,
    )
    print(json.dumps(ledger.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
