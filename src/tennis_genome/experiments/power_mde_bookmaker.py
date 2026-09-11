from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from tennis_genome.experiments.market_book_gate import load_confirmatory_market_book_qa
from tennis_genome.experiments.market_book_inputs import load_bookmaker_closing_rows
from tennis_genome.experiments.market_edge import SignalName, Tour
from tennis_genome.experiments.market_edge_inputs import (
    SignalValue,
    load_genome_values,
    load_match_years,
    load_profile_gap_values,
)
from tennis_genome.experiments.power_mde import (
    PowerMdeArtifact,
    PowerMdeRow,
    run_power_mde_claim,
)

_EXPERIMENT_ID = "POWER-MDE-001"
_METHOD = "null_fisher_information_wald_planning_v1"
_FAMILY_ALPHA = 0.05
_FAMILY_SIZE = 4
_PLANNING_ALPHA = 0.0125
_MIN_PRIOR_ROWS = 1000
_BETA_GRID = (0.02, 0.05, 0.10, 0.15, 0.20)
_REFERENCE_MARKET_PROBABILITIES = (0.50, 0.65, 0.80)
_CLAIMS: tuple[tuple[Tour, SignalName], ...] = (
    ("ATP", "profile_gap"),
    ("WTA", "profile_gap"),
    ("ATP", "genome"),
    ("WTA", "genome"),
)


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


def _power_rows(
    *,
    close_rows,
    signals: dict[str, SignalValue],
    years_by_match: dict[str, int],
    tour: Tour,
) -> list[PowerMdeRow]:
    shared = sorted(set(close_rows).intersection(signals, years_by_match))
    rows: list[PowerMdeRow] = []
    for match_id in shared:
        market = close_rows[match_id]
        if market.tour != tour:
            continue
        rows.append(
            PowerMdeRow(
                match_id=match_id,
                tour=tour,
                year=int(years_by_match[match_id]),
                market_probability_a=market.market_probability_a,
                signal=signals[match_id].signal,
            )
        )
    return sorted(rows, key=lambda row: (row.year, row.match_id))


def _signal_values(
    path: str | Path,
    *,
    tour: Tour,
    signal_name: SignalName,
) -> dict[str, SignalValue]:
    if signal_name == "profile_gap":
        return load_profile_gap_values(path, tour=tour)
    return load_genome_values(path, tour=tour)


def build_bookmaker_power_mde_artifact(
    *,
    market_book_qa: str | Path,
    market_book_records: str | Path,
    pre_match: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    min_prior_rows: int = _MIN_PRIOR_ROWS,
) -> PowerMdeArtifact:
    """Run frozen POWER-MDE-001 with outcome-blind BOOKMAKER_CLOSE_V1 probabilities."""

    qa_status = load_confirmatory_market_book_qa(market_book_qa)
    if set(qa_status) != {"ATP", "WTA"}:
        raise ValueError("MARKET-BOOK-QA must approve ATP and WTA before POWER-MDE")

    paths = {
        "market_book_qa": Path(market_book_qa),
        "market_book_records": Path(market_book_records),
        "pre_match": Path(pre_match),
        "profile_gap_atp": Path(profile_gap_atp),
        "profile_gap_wta": Path(profile_gap_wta),
        "genome_atp": Path(genome_atp),
        "genome_wta": Path(genome_wta),
    }
    close_rows = load_bookmaker_closing_rows(paths["market_book_records"])
    years_by_match = load_match_years(paths["pre_match"])
    signal_paths = {
        ("ATP", "profile_gap"): paths["profile_gap_atp"],
        ("WTA", "profile_gap"): paths["profile_gap_wta"],
        ("ATP", "genome"): paths["genome_atp"],
        ("WTA", "genome"): paths["genome_wta"],
    }

    claims = []
    for tour, signal_name in _CLAIMS:
        signals = _signal_values(
            signal_paths[(tour, signal_name)],
            tour=tour,
            signal_name=signal_name,
        )
        rows = _power_rows(
            close_rows=close_rows,
            signals=signals,
            years_by_match=years_by_match,
            tour=tour,
        )
        claims.append(
            run_power_mde_claim(
                rows,
                signal_name=signal_name,
                min_prior_rows=min_prior_rows,
            )
        )

    input_hashes = {name: _sha256_file(path) for name, path in sorted(paths.items())}
    unsigned = {
        "experiment_id": _EXPERIMENT_ID,
        "outcome_blind": True,
        "method": _METHOD,
        "family_alpha": _FAMILY_ALPHA,
        "family_size": _FAMILY_SIZE,
        "conservative_planning_alpha": _PLANNING_ALPHA,
        "beta_grid": _BETA_GRID,
        "reference_market_probabilities": _REFERENCE_MARKET_PROBABILITIES,
        "input_sha256": input_hashes,
        "claims": [asdict(claim) for claim in claims],
    }
    artifact_hash = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return PowerMdeArtifact(
        experiment_id=_EXPERIMENT_ID,
        outcome_blind=True,
        method=_METHOD,
        family_alpha=_FAMILY_ALPHA,
        family_size=_FAMILY_SIZE,
        conservative_planning_alpha=_PLANNING_ALPHA,
        beta_grid=_BETA_GRID,
        reference_market_probabilities=_REFERENCE_MARKET_PROBABILITIES,
        input_sha256=input_hashes,
        claims=tuple(claims),
        artifact_sha256=artifact_hash,
    )


def write_bookmaker_power_mde_artifact(artifact: PowerMdeArtifact, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen POWER-MDE-001 on QA-approved bookmaker closes"
    )
    parser.add_argument("--market-book-qa", required=True, type=Path)
    parser.add_argument("--market-book-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)
    parser.add_argument("--min-prior-rows", type=int, default=_MIN_PRIOR_ROWS)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = build_bookmaker_power_mde_artifact(
        market_book_qa=args.market_book_qa,
        market_book_records=args.market_book_records,
        pre_match=args.pre_match,
        profile_gap_atp=args.profile_gap_atp,
        profile_gap_wta=args.profile_gap_wta,
        genome_atp=args.genome_atp,
        genome_wta=args.genome_wta,
        min_prior_rows=args.min_prior_rows,
    )
    write_bookmaker_power_mde_artifact(artifact, args.output)
    print(json.dumps(artifact.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
