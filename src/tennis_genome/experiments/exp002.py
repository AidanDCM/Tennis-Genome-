from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import groupby
from pathlib import Path

from tennis_genome.data.canonical import HistoricalMatch, Surface
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.evaluation.walkforward import (
    ModelPrediction,
    walk_forward_elo,
    walk_forward_surface_elo,
)
from tennis_genome.ratings.elo import EloConfig


@dataclass(frozen=True)
class ModelScore:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class SliceComparison:
    slice_type: str
    slice_value: str
    n: int
    elo: ModelScore
    surface_elo: ModelScore
    brier_improvement_surface_vs_elo: float
    log_loss_improvement_surface_vs_elo: float
    accuracy_change_surface_vs_elo: float


@dataclass(frozen=True)
class Exp002Report:
    experiment_id: str
    population_n: int
    initial_rating: float
    k_factor: float
    scale: float
    elo: ModelScore
    surface_elo: ModelScore
    brier_improvement_surface_vs_elo: float
    log_loss_improvement_surface_vs_elo: float
    accuracy_change_surface_vs_elo: float
    yearly: tuple[SliceComparison, ...]
    by_surface: tuple[SliceComparison, ...]
    by_surface_experience: tuple[SliceComparison, ...]


def _score(y_true: list[bool], probabilities: list[float]) -> ModelScore:
    return ModelScore(
        n=len(y_true),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
        ece_10=expected_calibration_error(y_true, probabilities, n_bins=10),
    )


def _comparison_for_ids(
    ids: list[str],
    *,
    outcomes_by_id: dict[str, bool],
    elo_by_id: dict[str, ModelPrediction],
    surface_by_id: dict[str, ModelPrediction],
    slice_type: str,
    slice_value: str,
) -> SliceComparison:
    y_true = [outcomes_by_id[match_id] for match_id in ids]
    elo_probs = [elo_by_id[match_id].probability_a for match_id in ids]
    surface_probs = [surface_by_id[match_id].probability_a for match_id in ids]
    elo_score = _score(y_true, elo_probs)
    surface_score = _score(y_true, surface_probs)
    return SliceComparison(
        slice_type=slice_type,
        slice_value=slice_value,
        n=len(ids),
        elo=elo_score,
        surface_elo=surface_score,
        brier_improvement_surface_vs_elo=elo_score.brier - surface_score.brier,
        log_loss_improvement_surface_vs_elo=elo_score.log_loss - surface_score.log_loss,
        accuracy_change_surface_vs_elo=surface_score.accuracy - elo_score.accuracy,
    )


def _surface_experience_by_match(
    matches: list[HistoricalMatch],
    *,
    exclude_retirements: bool,
) -> dict[str, int]:
    """Return the weaker player's prior match count on the target surface.

    Counts use the same conservative date-only timing policy as Elo: all matches
    on one date see experience accumulated only through earlier dates. This makes
    the diagnostic legal at prediction time and insensitive to arbitrary CSV row
    order within a day.
    """
    ordered = sorted(
        matches,
        key=lambda match: (match.pre_match.event_date, match.match_id),
    )
    counts: defaultdict[tuple[str, Surface], int] = defaultdict(int)
    prior_minimum: dict[str, int] = {}

    for _, grouped in groupby(ordered, key=lambda match: match.pre_match.event_date):
        day_matches = [
            match
            for match in grouped
            if not match.outcome.walkover
            and not (exclude_retirements and match.outcome.retirement)
            and match.pre_match.surface != "Unknown"
        ]
        for match in day_matches:
            state = match.pre_match
            key_a = (state.player_a_id, state.surface)
            key_b = (state.player_b_id, state.surface)
            prior_minimum[match.match_id] = min(counts[key_a], counts[key_b])

        for match in day_matches:
            state = match.pre_match
            counts[(state.player_a_id, state.surface)] += 1
            counts[(state.player_b_id, state.surface)] += 1

    return prior_minimum


def _experience_band(prior_matches: int) -> str:
    if prior_matches == 0:
        return "0"
    if prior_matches <= 4:
        return "1-4"
    if prior_matches <= 9:
        return "5-9"
    if prior_matches <= 24:
        return "10-24"
    return "25+"


def run_exp002(
    matches: list[HistoricalMatch],
    *,
    config: EloConfig | None = None,
    exclude_retirements: bool = True,
) -> Exp002Report:
    """EXP-002: test whether pure surface Elo improves on overall Elo.

    Both models receive the same known-surface historical match stream. This
    prevents overall Elo from gaining extra training information from matches
    whose surface is unavailable to the surface-specialized model.
    """
    config = config or EloConfig()
    known_surface_matches = [
        match for match in matches if match.pre_match.surface != "Unknown"
    ]
    if not known_surface_matches:
        raise ValueError("EXP-002 requires at least one known-surface match")

    elo_predictions = walk_forward_elo(
        known_surface_matches,
        config=config,
        exclude_retirements=exclude_retirements,
    )
    surface_predictions = walk_forward_surface_elo(
        known_surface_matches,
        config=config,
        exclude_retirements=exclude_retirements,
    )
    surface_experience = _surface_experience_by_match(
        known_surface_matches,
        exclude_retirements=exclude_retirements,
    )

    outcomes_by_id = {
        match.match_id: match.outcome.a_won for match in known_surface_matches
    }
    surface_name_by_id: dict[str, Surface] = {
        match.match_id: match.pre_match.surface for match in known_surface_matches
    }
    elo_by_id = {prediction.match_id: prediction for prediction in elo_predictions}
    surface_by_id = {
        prediction.match_id: prediction for prediction in surface_predictions
    }
    common_ids = sorted(
        set(elo_by_id).intersection(surface_by_id),
        key=lambda match_id: (elo_by_id[match_id].event_date, match_id),
    )
    if not common_ids:
        raise ValueError("no common walk-forward predictions are available for EXP-002")

    y_true = [outcomes_by_id[match_id] for match_id in common_ids]
    elo_probs = [elo_by_id[match_id].probability_a for match_id in common_ids]
    surface_probs = [surface_by_id[match_id].probability_a for match_id in common_ids]
    elo_score = _score(y_true, elo_probs)
    surface_score = _score(y_true, surface_probs)

    ids_by_year: dict[int, list[str]] = {}
    ids_by_surface: dict[Surface, list[str]] = {}
    ids_by_experience: dict[str, list[str]] = {}
    for match_id in common_ids:
        year = elo_by_id[match_id].event_date.year
        ids_by_year.setdefault(year, []).append(match_id)
        surface = surface_name_by_id[match_id]
        ids_by_surface.setdefault(surface, []).append(match_id)
        band = _experience_band(surface_experience[match_id])
        ids_by_experience.setdefault(band, []).append(match_id)

    yearly = tuple(
        _comparison_for_ids(
            ids,
            outcomes_by_id=outcomes_by_id,
            elo_by_id=elo_by_id,
            surface_by_id=surface_by_id,
            slice_type="year",
            slice_value=str(year),
        )
        for year, ids in sorted(ids_by_year.items())
    )
    by_surface = tuple(
        _comparison_for_ids(
            ids,
            outcomes_by_id=outcomes_by_id,
            elo_by_id=elo_by_id,
            surface_by_id=surface_by_id,
            slice_type="surface",
            slice_value=surface,
        )
        for surface, ids in sorted(ids_by_surface.items())
    )
    experience_order = {"0": 0, "1-4": 1, "5-9": 2, "10-24": 3, "25+": 4}
    by_surface_experience = tuple(
        _comparison_for_ids(
            ids,
            outcomes_by_id=outcomes_by_id,
            elo_by_id=elo_by_id,
            surface_by_id=surface_by_id,
            slice_type="surface_experience",
            slice_value=band,
        )
        for band, ids in sorted(
            ids_by_experience.items(),
            key=lambda item: experience_order[item[0]],
        )
    )

    return Exp002Report(
        experiment_id="EXP-002",
        population_n=len(common_ids),
        initial_rating=config.initial_rating,
        k_factor=config.k_factor,
        scale=config.scale,
        elo=elo_score,
        surface_elo=surface_score,
        brier_improvement_surface_vs_elo=elo_score.brier - surface_score.brier,
        log_loss_improvement_surface_vs_elo=elo_score.log_loss - surface_score.log_loss,
        accuracy_change_surface_vs_elo=surface_score.accuracy - elo_score.accuracy,
        yearly=yearly,
        by_surface=by_surface,
        by_surface_experience=by_surface_experience,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXP-002: overall Elo versus surface Elo")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--initial-rating", type=float, default=1500.0)
    parser.add_argument("--k-factor", type=float, default=32.0)
    parser.add_argument("--scale", type=float, default=400.0)
    parser.add_argument(
        "--include-retirements",
        action="store_true",
        help="Include retirement matches; walkovers remain excluded",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    verify_canonical_manifest(
        manifest_path=args.manifest,
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        require_research_permission=True,
    )
    matches = load_canonical_parquet(
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
    )
    report = run_exp002(
        matches,
        config=EloConfig(
            initial_rating=args.initial_rating,
            k_factor=args.k_factor,
            scale=args.scale,
        ),
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
