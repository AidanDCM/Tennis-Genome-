from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tennis_genome.experiments.market_book_gate import load_confirmatory_market_book_qa
from tennis_genome.experiments.market_book_inputs import load_bookmaker_closing_rows
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
    load_match_years,
    load_settled_outcomes,
)

_EXPERIMENT_ID = "MARKET-EDGE-ADV-001"
_MARKET_POLICY = "BOOKMAKER_CLOSE_V1"
_MARKET_PROBABILITY_METHOD = "proportional_novig_two_way"
_DEVELOPMENT_END_YEAR = 2025
_CLAIMS: tuple[tuple[Tour, SignalName], ...] = (
    ("ATP", "profile_gap"),
    ("WTA", "profile_gap"),
    ("ATP", "genome"),
    ("WTA", "genome"),
)


@dataclass(frozen=True)
class BookmakerAdversarialClaimCoverage:
    tour: Tour
    signal_name: SignalName
    bookmaker_close_rows_for_tour: int
    frozen_core_signal_rows: int
    settled_outcome_rows: int
    matched_claim_rows: int


@dataclass(frozen=True)
class BookmakerMarketEdgeAdversarialArtifact:
    experiment_id: str
    development_end_year: int
    market_policy: str
    market_probability_method: str
    qa_required: bool
    qa_tour_status: dict[str, str]
    input_sha256: dict[str, str]
    coverage: tuple[BookmakerAdversarialClaimCoverage, ...]
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


def _model_values(
    path: str | Path,
    *,
    tour: Tour,
    signal_name: SignalName,
) -> dict[str, FrozenCoreSignalValue]:
    if signal_name == "profile_gap":
        return load_profile_gap_core_signal(path, tour=tour)
    return load_genome_core_signal(path, tour=tour)


def build_bookmaker_market_edge_adversarial_artifact(
    *,
    market_book_qa: str | Path,
    market_book_records: str | Path,
    pre_match: str | Path,
    outcomes_path: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    min_prior_rows: int = 1000,
) -> BookmakerMarketEdgeAdversarialArtifact:
    qa_status = load_confirmatory_market_book_qa(market_book_qa)
    close_rows = load_bookmaker_closing_rows(market_book_records)
    outcomes = load_settled_outcomes(outcomes_path)
    years_by_match = load_match_years(pre_match)

    model_paths: dict[tuple[Tour, SignalName], Path] = {
        ("ATP", "profile_gap"): Path(profile_gap_atp),
        ("WTA", "profile_gap"): Path(profile_gap_wta),
        ("ATP", "genome"): Path(genome_atp),
        ("WTA", "genome"): Path(genome_wta),
    }
    claim_rows: dict[tuple[Tour, SignalName], list[MarketCoreSignalRow]] = {}
    coverage: list[BookmakerAdversarialClaimCoverage] = []
    for tour, signal_name in _CLAIMS:
        model_values = _model_values(
            model_paths[(tour, signal_name)],
            tour=tour,
            signal_name=signal_name,
        )
        rows = build_market_core_signal_rows(
            close_rows=close_rows,  # type: ignore[arg-type]
            outcomes=outcomes,
            model_values=model_values,
            years_by_match=years_by_match,
            tour=tour,
            signal_name=signal_name,
        )
        if any(row.year > _DEVELOPMENT_END_YEAR for row in rows):
            raise ValueError("MARKET-EDGE-ADV-001 bookmaker run is frozen through 2025")
        claim_rows[(tour, signal_name)] = rows
        coverage.append(
            BookmakerAdversarialClaimCoverage(
                tour=tour,
                signal_name=signal_name,
                bookmaker_close_rows_for_tour=sum(
                    row.tour == tour for row in close_rows.values()
                ),
                frozen_core_signal_rows=len(model_values),
                settled_outcome_rows=len(outcomes),
                matched_claim_rows=len(rows),
            )
        )

    family = run_market_edge_adversarial_family(
        claim_rows,
        min_prior_rows=min_prior_rows,
    )
    paths = {
        "market_book_qa": Path(market_book_qa),
        "market_book_records": Path(market_book_records),
        "pre_match": Path(pre_match),
        "outcomes": Path(outcomes_path),
        "profile_gap_atp": Path(profile_gap_atp),
        "profile_gap_wta": Path(profile_gap_wta),
        "genome_atp": Path(genome_atp),
        "genome_wta": Path(genome_wta),
    }
    input_hashes = {name: _sha256_file(path) for name, path in sorted(paths.items())}
    unsigned = {
        "experiment_id": _EXPERIMENT_ID,
        "development_end_year": _DEVELOPMENT_END_YEAR,
        "market_policy": _MARKET_POLICY,
        "market_probability_method": _MARKET_PROBABILITY_METHOD,
        "qa_required": True,
        "qa_tour_status": dict(sorted(qa_status.items())),
        "input_sha256": input_hashes,
        "coverage": [asdict(item) for item in coverage],
        "family_report": family.to_dict(),
    }
    artifact_hash = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return BookmakerMarketEdgeAdversarialArtifact(
        experiment_id=_EXPERIMENT_ID,
        development_end_year=_DEVELOPMENT_END_YEAR,
        market_policy=_MARKET_POLICY,
        market_probability_method=_MARKET_PROBABILITY_METHOD,
        qa_required=True,
        qa_tour_status=dict(sorted(qa_status.items())),
        input_sha256=input_hashes,
        coverage=tuple(coverage),
        family_report=family.to_dict(),
        artifact_sha256=artifact_hash,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen MARKET-EDGE-ADV-001 on QA-approved bookmaker closes"
    )
    parser.add_argument("--market-book-qa", required=True, type=Path)
    parser.add_argument("--market-book-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)
    parser.add_argument("--min-prior-rows", type=int, default=1000)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = build_bookmaker_market_edge_adversarial_artifact(
        market_book_qa=args.market_book_qa,
        market_book_records=args.market_book_records,
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
