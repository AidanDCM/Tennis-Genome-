from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

Tour = Literal["ATP", "WTA"]
Surface = Literal["Hard", "Clay", "Grass", "Carpet", "Unknown"]


@dataclass(frozen=True)
class PreMatchState:
    """Information that is allowed to exist at prediction time.

    Outcome and post-match statistics are deliberately excluded. When a source
    row contains both pre- and post-match fields, adapters must split them into
    this structure plus ``MatchOutcome`` before modeling code sees the record.
    """

    match_id: str
    tour: Tour
    event_date: date
    source_order: int
    tournament_id: str
    tournament_name: str
    tournament_level: str | None
    surface: Surface
    round: str | None
    best_of: int | None
    player_a_id: str
    player_b_id: str
    player_a_name: str
    player_b_name: str
    rank_a: int | None
    rank_b: int | None
    rank_points_a: int | None
    rank_points_b: int | None


@dataclass(frozen=True)
class MatchOutcome:
    """Outcome-only fields that must never be passed into a pre-match model."""

    match_id: str
    a_won: bool
    score: str | None
    retirement: bool
    walkover: bool


@dataclass(frozen=True)
class HistoricalMatch:
    """Canonical historical match split into legal pre-match state and outcome."""

    pre_match: PreMatchState
    outcome: MatchOutcome

    def __post_init__(self) -> None:
        if self.pre_match.match_id != self.outcome.match_id:
            raise ValueError("pre_match and outcome match_id must agree")
        if self.pre_match.player_a_id == self.pre_match.player_b_id:
            raise ValueError("player_a_id and player_b_id must differ")

    @property
    def match_id(self) -> str:
        return self.pre_match.match_id
