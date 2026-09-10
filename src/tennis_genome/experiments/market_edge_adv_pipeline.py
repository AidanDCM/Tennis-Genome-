from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from tennis_genome.experiments.market_edge_adv_family import (
    run_market_edge_adversarial_family,
)
from tennis_genome.experiments.market_edge_adv_inputs import (
    FrozenCoreSignalValue,
    build_market_core_signal_rows,
    load_genome_core_signal,
    load_profile_gap_core_signal,
)
from tennis_genome.experiments.market_edge_adversarial import (
    MarketCoreSignalRow,
    SignalName,
    Tour,
)
from tennis_genome.experiments.market_edge_inputs import (
    load_closing_market_rows,
    load_match_years,
    load_settled_outcomes,
)

_EXPERIMENT_ID = "MARKET-EDGE-ADV-001"
_DEVELOPMENT_END_YEAR = 2025
_CLAIMS: tuple[tuple[Tour, SignalName], ...] = (
    ("ATP", "profile_gap"),
    ("WTA", "profile_gap"),
    ("ATP", "genome"),
    ("WTA", "genome"),
)


@dataclass(frozen=True)
class ClaimCoverage:
    tour: Tour
    signal_name: SignalName
    executable_close_rows_for_tour: int
    frozen_core_signal_rows: int
    settled_outcome_rows: int
    matched_claim_rows: int


@dataclass(frozen=True)
class MarketEdgeAdversarialArtifact:
    experiment_id: str
    development_end_year: int
    market_probability_method: str
    qa_required: bool
    qa_tour_status: dict[str, str]
    input_sha256: dict[str, str]
    coverage: tuple[ClaimCoverage, ...]
    family_report: dict[str, object]
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


def _load_qa_tour_status(path: str | Path) -> dict[Tour, str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MARKET-HIST-QA artifact must be a JSON object")
    if payload.get("experiment_id") != "MARKET-HIST-QA-001":
        raise ValueError("unexpected MARKET-HIST-QA experiment ID")
    if payload.get("effective_overall_status") == "BLOCKED_STRUCTURAL":
        raise ValueError("MARKET-HIST-QA is structurally blocked")
    qa_report = payload.get("qa_report")
    if not isinstance(qa_report, dict):
        raise ValueError("MARKET-HIST-QA artifact lacks qa_report")
    tours = qa_report.get("tours")
    if not isinstance(tours, list):
        raise ValueError("MARKET-HIST-QA qa_report.tours must be a list")
    result: dict[Tour, str] = {}
    for item in tours:
        if not isinstance(item, dict):
            raise ValueError("invalid MARKET-HIST-QA tour row")
        tour_text = str(item.get("tour", ""))
        if tour_text not in {"ATP", "WTA"}:
            raise ValueError(f"invalid MARKET-HIST-QA tour: {tour_text!r}")
        tour = cast(Tour, tour_text)
        if tour in result:
            raise ValueError(f"duplicate MARKET-HIST-QA tour status for {tour}")
        result[tour] = str(item.get("status", ""))
    if set(result) != {"ATP", "WTA"}:
        raise ValueError("MARKET-HIST-QA artifact must report ATP and WTA")
    return result


def _assert_confirmatory_tours(status: dict[Tour, str]) -> None:
    blocked = [tour for tour in ("ATP", "WTA") if status[tour] != "ELIGIBLE_CONFIRMATORY"]
    if blocked:
        raise ValueError(
            "MARKET-EDGE-ADV-001 confirmatory run requires QA-eligible ATP and WTA; "
            f"blocked={blocked}"
        )


def _build_claim(
    *,
    close_rows,
    outcomes,
    years_by_match,
    model_values: dict[str, FrozenCoreSignalValue],
    tour: Tour,
    signal_name: SignalName,
) -> tuple[list[MarketCoreSignalRow], ClaimCoverage]:
    rows = build_market_core_signal_rows(
        close_rows=close_rows,
        outcomes=outcomes,
        model_values=model_values,
        years_by_match=years_by_match,
        tour=tour,
        signal_name=signal_name,
    )
    if any(row.year > _DEVELOPMENT_END_YEAR for row in rows):
        raise ValueError("MARKET-EDGE-ADV-001 is frozen through 2025")
    return rows, ClaimCoverage(
        tour=tour,
        signal_name=signal_name,
        executable_close_rows_for_tour=sum(row.tour == tour for row in close_rows.values()),
        frozen_core_signal_rows=len(model_values),
        settled_outcome_rows=len(outcomes),
        matched_claim_rows=len(rows),
    )


def build_market_edge_adversarial_artifact(
    *,
    market_hist_qa: str | Path,
    market_hist_records: str | Path,
    pre_match: str | Path,
    outcomes_path: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    min_prior_rows: int = 1000,
) -> MarketEdgeAdversarialArtifact:
    paths = {
        "market_hist_qa": Path(market_hist_qa),
        "market_hist_records": Path(market_hist_records),
        "pre_match": Path(pre_match),
        "outcomes": Path(outcomes_path),
        "profile_gap_atp": Path(profile_gap_atp),
        "profile_gap_wta": Path(profile_gap_wta),
        "genome_atp": Path(genome_atp),
        "genome_wta": Path(genome_wta),
    }
    qa_status = _load_qa_tour_status(paths["market_hist_qa"])
    _assert_confirmatory_tours(qa_status)

    close_rows = load_closing_market_rows(paths["market_hist_records"])
    outcomes = load_settled_outcomes(paths["outcomes"])
    years_by_match = load_match_years(paths["pre_match"])
    if any(year > _DEVELOPMENT_END_YEAR for year in years_by_match.values()):
        raise ValueError("MARKET-EDGE-ADV-001 canonical input contains post-2025 rows")

    model_sets: dict[tuple[Tour, SignalName], dict[str, FrozenCoreSignalValue]] = {
        ("ATP", "profile_gap"): load_profile_gap_core_signal(
            paths["profile_gap_atp"], tour="ATP"
        ),
        ("WTA", "profile_gap"): load_profile_gap_core_signal(
            paths["profile_gap_wta"], tour="WTA"
        ),
        ("ATP", "genome"): load_genome_core_signal(paths["genome_atp"], tour="ATP"),
        ("WTA", "genome"): load_genome_core_signal(paths["genome_wta"], tour="WTA"),
    }

    claim_rows: dict[tuple[Tour, SignalName], list[MarketCoreSignalRow]] = {}
    coverage: list[ClaimCoverage] = []
    for tour, signal_name in _CLAIMS:
        rows, claim_coverage = _build_claim(
            close_rows=close_rows,
            outcomes=outcomes,
            years_by_match=years_by_match,
            model_values=model_sets[(tour, signal_name)],
            tour=tour,
            signal_name=signal_name,
        )
        claim_rows[(tour, signal_name)] = rows
        coverage.append(claim_coverage)

    family = run_market_edge_adversarial_family(
        claim_rows,
        min_prior_rows=min_prior_rows,
    )
    input_sha256 = {name: _sha256_file(path) for name, path in sorted(paths.items())}
    payload_without_digest = {
        "experiment_id": _EXPERIMENT_ID,
        "development_end_year": _DEVELOPMENT_END_YEAR,
        "market_probability_method": "exchange_mid_implied_proportional_v1",
        "qa_required": True,
        "qa_tour_status": dict(sorted(qa_status.items())),
        "input_sha256": input_sha256,
        "coverage": [asdict(item) for item in coverage],
        "family_report": family.to_dict(),
    }
    artifact_digest = hashlib.sha256(_canonical_json_bytes(payload_without_digest)).hexdigest()
    return MarketEdgeAdversarialArtifact(
        experiment_id=_EXPERIMENT_ID,
        development_end_year=_DEVELOPMENT_END_YEAR,
        market_probability_method="exchange_mid_implied_proportional_v1",
        qa_required=True,
        qa_tour_status=dict(sorted(qa_status.items())),
        input_sha256=input_sha256,
        coverage=tuple(coverage),
        family_report=family.to_dict(),
        artifact_sha256=artifact_digest,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MARKET-EDGE-ADV-001 from QA-approved immutable artifacts"
    )
    parser.add_argument("--market-hist-qa", required=True, type=Path)
    parser.add_argument("--market-hist-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-prior-rows", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = build_market_edge_adversarial_artifact(
        market_hist_qa=args.market_hist_qa,
        market_hist_records=args.market_hist_records,
        pre_match=args.pre_match,
        outcomes_path=args.outcomes,
        profile_gap_atp=args.profile_gap_atp,
        profile_gap_wta=args.profile_gap_wta,
        genome_atp=args.genome_atp,
        genome_wta=args.genome_wta,
        min_prior_rows=args.min_prior_rows,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
