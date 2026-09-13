from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import groupby

from tennis_genome.data.canonical import HistoricalMatch, Surface
from tennis_genome.models.ranking import RankingLogitModel
from tennis_genome.ratings.elo import EloConfig, expected_score


@dataclass(frozen=True)
class ModelPrediction:
    """Pre-match model output only; realized outcomes live elsewhere."""

    match_id: str
    event_date: date
    model_name: str
    probability_a: float


def _eligible(match: HistoricalMatch, *, exclude_retirements: bool) -> bool:
    if match.outcome.walkover:
        return False
    if exclude_retirements and match.outcome.retirement:
        return False
    return True


def walk_forward_elo(
    matches: list[HistoricalMatch],
    *,
    config: EloConfig | None = None,
    exclude_retirements: bool = True,
) -> list[ModelPrediction]:
    """Generate pre-match Elo probabilities without same-day order leakage.

    Many public historical files provide a date but not a trustworthy start
    timestamp. All matches on the same date therefore see the ratings as they
    stood before that date. Rating deltas are computed from that frozen daily
    snapshot and applied simultaneously after the day's predictions.

    This is conservative: it may ignore legitimately available earlier same-day
    results, but it cannot invent knowledge from arbitrary CSV row ordering.
    """
    config = config or EloConfig()
    ordered = sorted(
        matches,
        key=lambda match: (match.pre_match.event_date, match.match_id),
    )
    ratings: dict[str, float] = {}
    predictions: list[ModelPrediction] = []

    for event_date, grouped in groupby(ordered, key=lambda match: match.pre_match.event_date):
        day_matches = [
            match for match in grouped if _eligible(match, exclude_retirements=exclude_retirements)
        ]
        deltas: defaultdict[str, float] = defaultdict(float)

        for match in day_matches:
            state = match.pre_match
            rating_a = ratings.get(state.player_a_id, config.initial_rating)
            rating_b = ratings.get(state.player_b_id, config.initial_rating)
            p_a = expected_score(rating_a, rating_b, scale=config.scale)
            predictions.append(
                ModelPrediction(
                    match_id=match.match_id,
                    event_date=event_date,
                    model_name="elo",
                    probability_a=p_a,
                )
            )

            y_a = 1.0 if match.outcome.a_won else 0.0
            delta_a = config.k_factor * (y_a - p_a)
            deltas[state.player_a_id] += delta_a
            deltas[state.player_b_id] -= delta_a

        for player_id, rating_delta in deltas.items():
            ratings[player_id] = ratings.get(player_id, config.initial_rating) + rating_delta

    return predictions


def walk_forward_surface_elo(
    matches: list[HistoricalMatch],
    *,
    config: EloConfig | None = None,
    exclude_retirements: bool = True,
) -> list[ModelPrediction]:
    """Generate pure surface-specific Elo probabilities chronologically.

    Each player owns an independent rating for Hard, Clay, Grass, and Carpet.
    Unknown-surface matches are skipped because assigning them to a surface
    would manufacture information. As with overall Elo, date-only datasets use
    a frozen pre-day snapshot and apply all same-day deltas simultaneously.

    This intentionally tests a simple surface specialization. It does not yet
    blend overall and surface ratings, share priors across surfaces, decay old
    results, or tune surface-specific K factors.
    """
    config = config or EloConfig()
    ordered = sorted(
        matches,
        key=lambda match: (match.pre_match.event_date, match.match_id),
    )
    ratings: dict[tuple[str, Surface], float] = {}
    predictions: list[ModelPrediction] = []

    for event_date, grouped in groupby(ordered, key=lambda match: match.pre_match.event_date):
        day_matches = [
            match
            for match in grouped
            if _eligible(match, exclude_retirements=exclude_retirements)
            and match.pre_match.surface != "Unknown"
        ]
        deltas: defaultdict[tuple[str, Surface], float] = defaultdict(float)

        for match in day_matches:
            state = match.pre_match
            surface = state.surface
            key_a = (state.player_a_id, surface)
            key_b = (state.player_b_id, surface)
            rating_a = ratings.get(key_a, config.initial_rating)
            rating_b = ratings.get(key_b, config.initial_rating)
            p_a = expected_score(rating_a, rating_b, scale=config.scale)
            predictions.append(
                ModelPrediction(
                    match_id=match.match_id,
                    event_date=event_date,
                    model_name="surface_elo",
                    probability_a=p_a,
                )
            )

            y_a = 1.0 if match.outcome.a_won else 0.0
            delta_a = config.k_factor * (y_a - p_a)
            deltas[key_a] += delta_a
            deltas[key_b] -= delta_a

        for rating_key, rating_delta in deltas.items():
            ratings[rating_key] = ratings.get(rating_key, config.initial_rating) + rating_delta

    return predictions


def walk_forward_ranking_logit(
    matches: list[HistoricalMatch],
    *,
    min_train_matches: int = 500,
    exclude_retirements: bool = True,
) -> list[ModelPrediction]:
    """Fit ranking calibration on prior years and predict the next year."""
    if min_train_matches <= 0:
        raise ValueError("min_train_matches must be positive")

    eligible = [
        match
        for match in matches
        if _eligible(match, exclude_retirements=exclude_retirements)
        and match.pre_match.rank_a is not None
        and match.pre_match.rank_b is not None
    ]
    if not eligible:
        return []

    predictions: list[ModelPrediction] = []
    years = sorted({match.pre_match.event_date.year for match in eligible})
    for test_year in years:
        train = [match for match in eligible if match.pre_match.event_date.year < test_year]
        test = [match for match in eligible if match.pre_match.event_date.year == test_year]
        if len(train) < min_train_matches or not test:
            continue

        rank_pairs = [
            (match.pre_match.rank_a, match.pre_match.rank_b)
            for match in train
            if match.pre_match.rank_a is not None and match.pre_match.rank_b is not None
        ]
        outcomes = [match.outcome.a_won for match in train]
        if len({bool(value) for value in outcomes}) < 2:
            continue

        model = RankingLogitModel().fit(rank_pairs, outcomes)
        for match in test:
            probability = model.predict_proba(
                match.pre_match.rank_a,
                match.pre_match.rank_b,
            )
            if probability is None:
                continue
            predictions.append(
                ModelPrediction(
                    match_id=match.match_id,
                    event_date=match.pre_match.event_date,
                    model_name="ranking_logit",
                    probability_a=probability,
                )
            )

    return predictions
