from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import cast

import pandas as pd

from tennis_genome.data.canonical import PreMatchState, Surface, Tour

_VALID_TOURS = {"ATP", "WTA"}
_VALID_SURFACES = {"Hard", "Clay", "Grass", "Carpet", "Unknown"}
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


def _event_date(value: object) -> date:
    if value is None or pd.isna(value):
        raise ValueError("canonical event_date cannot be missing")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


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


def load_market_pre_match_states(path: str | Path) -> list[PreMatchState]:
    """Load canonical market-join inputs while failing closed on outcome leakage."""

    frame = pd.read_parquet(Path(path))
    leaked = sorted(_PRE_MATCH_FORBIDDEN.intersection(frame.columns))
    if leaked:
        raise ValueError(f"outcome fields leaked into pre-match table: {leaked}")
    missing = sorted(_PRE_MATCH_REQUIRED.difference(frame.columns))
    if missing:
        raise ValueError(f"pre-match table missing required columns: {missing}")
    if frame["match_id"].astype(str).duplicated().any():
        raise ValueError("pre-match table contains duplicate match_id values")

    states: list[PreMatchState] = []
    for row in frame.itertuples(index=False):
        values = row._asdict()
        states.append(
            PreMatchState(
                match_id=str(values["match_id"]),
                tour=_tour(values["tour"]),
                event_date=_event_date(values["event_date"]),
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
        )
    return states
