from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast

import pandas as pd

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState, Surface, Tour
from tennis_genome.data.identity import canonical_player_id, orient_pair

_SURFACES: dict[str, Surface] = {
    "hard": "Hard",
    "clay": "Clay",
    "grass": "Grass",
    "carpet": "Carpet",
}


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "<na>"}:
        return None
    return int(float(text))


def _text(value: object, *, default: str = "") -> str:
    if value is None or pd.isna(value):
        return default
    return str(value).strip()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _parse_tourney_date(value: object) -> datetime.date:
    raw = _text(value)
    if not raw:
        raise ValueError("tourney_date is required")
    if raw.endswith(".0"):
        raw = raw[:-2]
    return datetime.strptime(raw, "%Y%m%d").date()


def _surface(value: object) -> Surface:
    text = _text(value).casefold()
    return _SURFACES.get(text, "Unknown")


def load_sackmann_csv(path: str | Path, *, tour: Tour) -> list[HistoricalMatch]:
    """Load a Jeff-Sackmann-style match CSV into the canonical contract.

    This adapter intentionally does not download data. Callers provide a local
    CSV and remain responsible for verifying source provenance, license, and the
    timestamp semantics of fields such as rankings before using them in a final
    experiment.

    The source format stores winner fields first. A/B orientation is therefore
    rebuilt from stable player IDs so the target label cannot leak through row
    layout.
    """
    frame = pd.read_csv(path, low_memory=False)
    required = {
        "tourney_id",
        "tourney_name",
        "tourney_date",
        "winner_name",
        "loser_name",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"missing required source columns: {missing}")

    matches: list[HistoricalMatch] = []
    for source_order, row in frame.iterrows():
        winner_name = _text(row.get("winner_name"))
        loser_name = _text(row.get("loser_name"))
        if not winner_name or not loser_name:
            raise ValueError(f"row {source_order} has an empty winner/loser name")

        winner_id = canonical_player_id(
            tour=tour, source_id=row.get("winner_id"), name=winner_name
        )
        loser_id = canonical_player_id(tour=tour, source_id=row.get("loser_id"), name=loser_name)
        player_a_id, player_b_id, player_a_name, player_b_name, a_won = orient_pair(
            winner_id=winner_id,
            loser_id=loser_id,
            winner_name=winner_name,
            loser_name=loser_name,
        )

        tournament_id = _text(row.get("tourney_id"), default="unknown")
        match_num = _optional_int(row.get("match_num"))
        match_suffix = str(match_num) if match_num is not None else f"row-{source_order}"
        match_id = f"{tour.lower()}:{tournament_id}:{match_suffix}"

        winner_rank = _optional_int(row.get("winner_rank"))
        loser_rank = _optional_int(row.get("loser_rank"))
        winner_points = _optional_int(row.get("winner_rank_points"))
        loser_points = _optional_int(row.get("loser_rank_points"))
        rank_a, rank_b = (winner_rank, loser_rank) if a_won else (loser_rank, winner_rank)
        points_a, points_b = (
            (winner_points, loser_points) if a_won else (loser_points, winner_points)
        )

        score = _optional_text(row.get("score"))
        score_upper = (score or "").upper()
        pre_match = PreMatchState(
            match_id=match_id,
            tour=tour,
            event_date=_parse_tourney_date(row.get("tourney_date")),
            source_order=int(source_order),
            tournament_id=tournament_id,
            tournament_name=_text(row.get("tourney_name"), default="unknown"),
            tournament_level=_optional_text(row.get("tourney_level")),
            surface=_surface(row.get("surface")),
            round=_optional_text(row.get("round")),
            best_of=_optional_int(row.get("best_of")),
            player_a_id=player_a_id,
            player_b_id=player_b_id,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
            rank_a=rank_a,
            rank_b=rank_b,
            rank_points_a=points_a,
            rank_points_b=points_b,
        )
        outcome = MatchOutcome(
            match_id=match_id,
            a_won=a_won,
            score=score,
            retirement="RET" in score_upper,
            walkover="W/O" in score_upper or "WO" == score_upper,
        )
        matches.append(HistoricalMatch(pre_match=pre_match, outcome=outcome))

    return cast(list[HistoricalMatch], matches)
