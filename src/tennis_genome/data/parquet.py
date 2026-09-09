from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import cast

import pandas as pd

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    PreMatchState,
    Surface,
    Tour,
)

_PRE_MATCH_FORBIDDEN = {"a_won", "score", "retirement", "walkover"}
_OUTCOME_REQUIRED = {"match_id", "a_won", "score", "retirement", "walkover"}
_VALID_TOURS = {"ATP", "WTA"}
_VALID_SURFACES = {"Hard", "Clay", "Grass", "Carpet", "Unknown"}


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _optional_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text if text else None


def _tour(value: object) -> Tour:
    text = str(value)
    if text not in _VALID_TOURS:
        raise ValueError(f"invalid canonical tour: {text}")
    return cast(Tour, text)


def _surface(value: object) -> Surface:
    text = str(value)
    if text not in _VALID_SURFACES:
        raise ValueError(f"invalid canonical surface: {text}")
    return cast(Surface, text)


def load_canonical_parquet(
    *,
    pre_match_path: Path,
    outcome_path: Path,
) -> list[HistoricalMatch]:
    """Load canonical pre-match and outcome tables into HistoricalMatch records.

    Modeling code should prefer this boundary over source-specific adapters.
    The loader fails closed if outcome fields appear in the pre-match table or
    if the two tables do not contain exactly the same match IDs.
    """
    pre_match = pd.read_parquet(pre_match_path)
    outcomes = pd.read_parquet(outcome_path)

    leaked = sorted(_PRE_MATCH_FORBIDDEN.intersection(pre_match.columns))
    if leaked:
        raise ValueError(f"outcome fields leaked into pre-match table: {leaked}")
    missing_outcome = sorted(_OUTCOME_REQUIRED.difference(outcomes.columns))
    if missing_outcome:
        raise ValueError(f"outcome table missing required columns: {missing_outcome}")

    if pre_match["match_id"].duplicated().any():
        raise ValueError("pre-match table contains duplicate match_id values")
    if outcomes["match_id"].duplicated().any():
        raise ValueError("outcome table contains duplicate match_id values")

    pre_ids = set(pre_match["match_id"].astype(str))
    outcome_ids = set(outcomes["match_id"].astype(str))
    if pre_ids != outcome_ids:
        missing_outcomes = sorted(pre_ids - outcome_ids)[:10]
        missing_states = sorted(outcome_ids - pre_ids)[:10]
        raise ValueError(
            "canonical table match IDs differ; "
            f"missing_outcomes={missing_outcomes}, missing_pre_match={missing_states}"
        )

    outcome_by_id = outcomes.set_index("match_id", drop=False)
    matches: list[HistoricalMatch] = []
    for row in pre_match.itertuples(index=False):
        values = row._asdict()
        match_id = str(values["match_id"])
        outcome_values = outcome_by_id.loc[match_id]

        state = PreMatchState(
            match_id=match_id,
            tour=_tour(values["tour"]),
            event_date=_date_value(values["event_date"]),
            source_order=int(values["source_order"]),
            tournament_id=str(values["tournament_id"]),
            tournament_name=str(values["tournament_name"]),
            tournament_level=_optional_text(values.get("tournament_level")),
            surface=_surface(values["surface"]),
            round=_optional_text(values.get("round")),
            best_of=_optional_int(values.get("best_of")),
            player_a_id=str(values["player_a_id"]),
            player_b_id=str(values["player_b_id"]),
            player_a_name=str(values["player_a_name"]),
            player_b_name=str(values["player_b_name"]),
            rank_a=_optional_int(values.get("rank_a")),
            rank_b=_optional_int(values.get("rank_b")),
            rank_points_a=_optional_int(values.get("rank_points_a")),
            rank_points_b=_optional_int(values.get("rank_points_b")),
        )
        outcome = MatchOutcome(
            match_id=match_id,
            a_won=bool(outcome_values["a_won"]),
            score=_optional_text(outcome_values["score"]),
            retirement=bool(outcome_values["retirement"]),
            walkover=bool(outcome_values["walkover"]),
        )
        matches.append(HistoricalMatch(pre_match=state, outcome=outcome))

    return matches
