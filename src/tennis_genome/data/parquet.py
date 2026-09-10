from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import cast

import pandas as pd

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
    Surface,
    Tour,
)

_PRE_MATCH_FORBIDDEN = {"a_won", "score", "retirement", "walkover"}
_PRE_MATCH_REQUIRED = {
    "match_id",
    "tour",
    "event_date",
    "source_order",
    "tournament_id",
    "tournament_name",
    "tournament_level",
    "surface",
    "round",
    "best_of",
    "player_a_id",
    "player_b_id",
    "player_a_name",
    "player_b_name",
    "rank_a",
    "rank_b",
    "rank_points_a",
    "rank_points_b",
}
_OUTCOME_REQUIRED = {"match_id", "a_won", "score", "retirement", "walkover"}
_STATS_REQUIRED = {
    "match_id",
    "aces_a",
    "aces_b",
    "double_faults_a",
    "double_faults_b",
    "service_points_a",
    "service_points_b",
    "first_serves_in_a",
    "first_serves_in_b",
    "first_serve_points_won_a",
    "first_serve_points_won_b",
    "second_serve_points_won_a",
    "second_serve_points_won_b",
    "service_games_a",
    "service_games_b",
    "break_points_saved_a",
    "break_points_saved_b",
    "break_points_faced_a",
    "break_points_faced_b",
}
_STATS_FORBIDDEN = {"a_won", "score", "retirement", "walkover"}
_VALID_TOURS = {"ATP", "WTA"}
_VALID_SURFACES = {"Hard", "Clay", "Grass", "Carpet", "Unknown"}


def _date_value(value: object) -> date:
    if value is None or pd.isna(value):
        raise ValueError("canonical event_date cannot be missing")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text if text else None


def _required_bool(value: object, *, field: str, match_id: str) -> bool:
    if value is None or pd.isna(value):
        raise ValueError(f"{field} is missing for match {match_id}")
    if value not in (True, False, 0, 1):
        raise ValueError(f"{field} is not boolean for match {match_id}: {value!r}")
    return bool(value)


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


def _stats_from_row(values: dict[str, object]) -> MatchStats:
    return MatchStats(
        match_id=str(values["match_id"]),
        aces_a=_optional_int(values.get("aces_a")),
        aces_b=_optional_int(values.get("aces_b")),
        double_faults_a=_optional_int(values.get("double_faults_a")),
        double_faults_b=_optional_int(values.get("double_faults_b")),
        service_points_a=_optional_int(values.get("service_points_a")),
        service_points_b=_optional_int(values.get("service_points_b")),
        first_serves_in_a=_optional_int(values.get("first_serves_in_a")),
        first_serves_in_b=_optional_int(values.get("first_serves_in_b")),
        first_serve_points_won_a=_optional_int(values.get("first_serve_points_won_a")),
        first_serve_points_won_b=_optional_int(values.get("first_serve_points_won_b")),
        second_serve_points_won_a=_optional_int(
            values.get("second_serve_points_won_a")
        ),
        second_serve_points_won_b=_optional_int(
            values.get("second_serve_points_won_b")
        ),
        service_games_a=_optional_int(values.get("service_games_a")),
        service_games_b=_optional_int(values.get("service_games_b")),
        break_points_saved_a=_optional_int(values.get("break_points_saved_a")),
        break_points_saved_b=_optional_int(values.get("break_points_saved_b")),
        break_points_faced_a=_optional_int(values.get("break_points_faced_a")),
        break_points_faced_b=_optional_int(values.get("break_points_faced_b")),
        duration_minutes=_optional_int(values.get("duration_minutes")),
    )


def load_canonical_parquet(
    *,
    pre_match_path: Path,
    outcome_path: Path,
    stats_path: Path | None = None,
) -> list[HistoricalMatch]:
    """Load canonical tables while preserving information-class boundaries."""
    pre_match = pd.read_parquet(pre_match_path)
    outcomes = pd.read_parquet(outcome_path)
    stats = pd.read_parquet(stats_path) if stats_path is not None else None

    leaked = sorted(_PRE_MATCH_FORBIDDEN.intersection(pre_match.columns))
    if leaked:
        raise ValueError(f"outcome fields leaked into pre-match table: {leaked}")
    missing_pre_match = sorted(_PRE_MATCH_REQUIRED.difference(pre_match.columns))
    if missing_pre_match:
        raise ValueError(f"pre-match table missing required columns: {missing_pre_match}")
    missing_outcome = sorted(_OUTCOME_REQUIRED.difference(outcomes.columns))
    if missing_outcome:
        raise ValueError(f"outcome table missing required columns: {missing_outcome}")

    pre_match = pre_match.copy()
    outcomes = outcomes.copy()
    pre_match["match_id"] = pre_match["match_id"].astype(str)
    outcomes["match_id"] = outcomes["match_id"].astype(str)

    if pre_match["match_id"].duplicated().any():
        raise ValueError("pre-match table contains duplicate match_id values")
    if outcomes["match_id"].duplicated().any():
        raise ValueError("outcome table contains duplicate match_id values")

    pre_ids = set(pre_match["match_id"])
    outcome_ids = set(outcomes["match_id"])
    if pre_ids != outcome_ids:
        raise ValueError(
            "canonical table match IDs differ; "
            f"missing_outcomes={sorted(pre_ids - outcome_ids)[:10]}, "
            f"missing_pre_match={sorted(outcome_ids - pre_ids)[:10]}"
        )

    stats_by_id: pd.DataFrame | None = None
    if stats is not None:
        leaked_stats = sorted(_STATS_FORBIDDEN.intersection(stats.columns))
        if leaked_stats:
            raise ValueError(f"outcome fields leaked into stats table: {leaked_stats}")
        missing_stats = sorted(_STATS_REQUIRED.difference(stats.columns))
        if missing_stats:
            raise ValueError(f"stats table missing required columns: {missing_stats}")
        stats = stats.copy()
        stats["match_id"] = stats["match_id"].astype(str)
        if stats["match_id"].duplicated().any():
            raise ValueError("stats table contains duplicate match_id values")
        stats_ids = set(stats["match_id"])
        if stats_ids != pre_ids:
            raise ValueError(
                "canonical stats match IDs differ; "
                f"missing_stats={sorted(pre_ids - stats_ids)[:10]}, "
                f"extra_stats={sorted(stats_ids - pre_ids)[:10]}"
            )
        stats_by_id = stats.set_index("match_id", drop=False)

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
            draw_size=_optional_int(values.get("draw_size")),
            seed_a=_optional_int(values.get("seed_a")),
            seed_b=_optional_int(values.get("seed_b")),
            entry_a=_optional_text(values.get("entry_a")),
            entry_b=_optional_text(values.get("entry_b")),
            hand_a=_optional_text(values.get("hand_a")),
            hand_b=_optional_text(values.get("hand_b")),
            height_cm_a=_optional_int(values.get("height_cm_a")),
            height_cm_b=_optional_int(values.get("height_cm_b")),
            age_years_a=_optional_float(values.get("age_years_a")),
            age_years_b=_optional_float(values.get("age_years_b")),
            ioc_a=_optional_text(values.get("ioc_a")),
            ioc_b=_optional_text(values.get("ioc_b")),
        )
        outcome = MatchOutcome(
            match_id=match_id,
            a_won=_required_bool(
                outcome_values["a_won"],
                field="a_won",
                match_id=match_id,
            ),
            score=_optional_text(outcome_values["score"]),
            retirement=_required_bool(
                outcome_values["retirement"],
                field="retirement",
                match_id=match_id,
            ),
            walkover=_required_bool(
                outcome_values["walkover"],
                field="walkover",
                match_id=match_id,
            ),
        )
        match_stats = None
        if stats_by_id is not None:
            stats_values = stats_by_id.loc[match_id].to_dict()
            match_stats = _stats_from_row(stats_values)
        matches.append(
            HistoricalMatch(
                pre_match=state,
                outcome=outcome,
                stats=match_stats,
            )
        )

    return matches
