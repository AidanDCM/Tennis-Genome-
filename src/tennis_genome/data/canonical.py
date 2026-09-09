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
    row contains both pre- and post-match fields, adapters must split them before
    modeling code sees the pre-match state.
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
class MatchStats:
    """Post-match statistics stored separately from legal pre-match state.

    These values describe what happened during the match. They may update a
    player's historical state only *after* the match/date has passed; the target
    match's own stats are never legal target-match features.
    """

    match_id: str
    aces_a: int | None = None
    aces_b: int | None = None
    double_faults_a: int | None = None
    double_faults_b: int | None = None
    service_points_a: int | None = None
    service_points_b: int | None = None
    first_serves_in_a: int | None = None
    first_serves_in_b: int | None = None
    first_serve_points_won_a: int | None = None
    first_serve_points_won_b: int | None = None
    second_serve_points_won_a: int | None = None
    second_serve_points_won_b: int | None = None
    service_games_a: int | None = None
    service_games_b: int | None = None
    break_points_saved_a: int | None = None
    break_points_saved_b: int | None = None
    break_points_faced_a: int | None = None
    break_points_faced_b: int | None = None

    @property
    def service_points_won_a(self) -> int | None:
        if self.first_serve_points_won_a is None or self.second_serve_points_won_a is None:
            return None
        return self.first_serve_points_won_a + self.second_serve_points_won_a

    @property
    def service_points_won_b(self) -> int | None:
        if self.first_serve_points_won_b is None or self.second_serve_points_won_b is None:
            return None
        return self.first_serve_points_won_b + self.second_serve_points_won_b


@dataclass(frozen=True)
class HistoricalMatch:
    """Canonical historical record with physically separable information classes."""

    pre_match: PreMatchState
    outcome: MatchOutcome
    stats: MatchStats | None = None

    def __post_init__(self) -> None:
        if self.pre_match.match_id != self.outcome.match_id:
            raise ValueError("pre_match and outcome match_id must agree")
        if self.stats is not None and self.pre_match.match_id != self.stats.match_id:
            raise ValueError("pre_match and stats match_id must agree")
        if self.pre_match.player_a_id == self.pre_match.player_b_id:
            raise ValueError("player_a_id and player_b_id must differ")

    @property
    def match_id(self) -> str:
        return self.pre_match.match_id
