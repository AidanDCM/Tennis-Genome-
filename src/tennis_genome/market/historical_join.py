from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from tennis_genome.data.canonical import PreMatchState, Tour
from tennis_genome.market.exchange_snapshot import ExchangeMarketSnapshot

JoinStatus = Literal["MATCHED", "UNMATCHED", "AMBIGUOUS"]
_JOIN_VERSION = "betfair-historical-join-v1"
_DEFAULT_DAYS_BEFORE = 4
_DEFAULT_DAYS_AFTER = 21


def normalize_market_player_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens: list[str] = []
    current: list[str] = []
    for char in without_marks.casefold():
        if char.isalnum():
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return " ".join(tokens)


@dataclass(frozen=True)
class HistoricalMarketJoin:
    join_hash: str
    resolver_version: str
    source_market_id: str
    source_event_id: str
    source_market_time: datetime
    match_id: str
    tour: Tour
    source_selection_a_id: int
    source_selection_b_id: int
    source_selection_a_name: str
    source_selection_b_name: str
    player_a_id: str
    player_b_id: str
    tournament_date_offset_days: int
    days_before_window: int
    days_after_window: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_market_time"] = self.source_market_time.isoformat()
        return payload


@dataclass(frozen=True)
class HistoricalMarketJoinResult:
    status: JoinStatus
    source_market_id: str
    source_event_id: str
    normalized_runner_names: tuple[str, str]
    candidate_match_ids: tuple[str, ...]
    join: HistoricalMarketJoin | None = None

    def __post_init__(self) -> None:
        if self.status == "MATCHED":
            if self.join is None or len(self.candidate_match_ids) != 1:
                raise ValueError("MATCHED join result requires exactly one join candidate")
        elif self.join is not None:
            raise ValueError("unmatched/ambiguous join result cannot contain a join")


def _pair_key(name_a: str, name_b: str) -> tuple[str, str]:
    return tuple(sorted((normalize_market_player_name(name_a), normalize_market_player_name(name_b))))  # type: ignore[return-value]


def _join_hash(
    *,
    snapshot: ExchangeMarketSnapshot,
    state: PreMatchState,
    source_selection_a_id: int,
    source_selection_b_id: int,
    days_before: int,
    days_after: int,
) -> str:
    key = "|".join(
        (
            _JOIN_VERSION,
            snapshot.source_market_id,
            snapshot.source_event_id,
            state.match_id,
            str(source_selection_a_id),
            str(source_selection_b_id),
            state.player_a_id,
            state.player_b_id,
            str(days_before),
            str(days_after),
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def resolve_betfair_market_to_pre_match(
    snapshot: ExchangeMarketSnapshot,
    pre_match_states: list[PreMatchState],
    *,
    days_before_tournament_start: int = _DEFAULT_DAYS_BEFORE,
    days_after_tournament_start: int = _DEFAULT_DAYS_AFTER,
) -> HistoricalMarketJoinResult:
    if days_before_tournament_start < 0 or days_after_tournament_start < 0:
        raise ValueError("join date-window values must be non-negative")
    if len(snapshot.runners) != 2:
        raise ValueError("Betfair historical join requires exactly two runners")

    runner_pair = _pair_key(
        snapshot.runners[0].selection_name,
        snapshot.runners[1].selection_name,
    )
    candidates: list[tuple[PreMatchState, int]] = []
    for state in pre_match_states:
        if _pair_key(state.player_a_name, state.player_b_name) != runner_pair:
            continue
        offset_days = (snapshot.market_time.date() - state.event_date).days
        if -days_before_tournament_start <= offset_days <= days_after_tournament_start:
            candidates.append((state, offset_days))

    candidate_ids = tuple(sorted(state.match_id for state, _ in candidates))
    normalized_names = tuple(sorted(runner_pair))
    if not candidates:
        return HistoricalMarketJoinResult(
            status="UNMATCHED",
            source_market_id=snapshot.source_market_id,
            source_event_id=snapshot.source_event_id,
            normalized_runner_names=normalized_names,
            candidate_match_ids=(),
        )
    if len(candidates) != 1:
        return HistoricalMarketJoinResult(
            status="AMBIGUOUS",
            source_market_id=snapshot.source_market_id,
            source_event_id=snapshot.source_event_id,
            normalized_runner_names=normalized_names,
            candidate_match_ids=candidate_ids,
        )

    state, offset_days = candidates[0]
    canonical_a = normalize_market_player_name(state.player_a_name)
    canonical_b = normalize_market_player_name(state.player_b_name)
    source_a = next(
        (
            runner
            for runner in snapshot.runners
            if normalize_market_player_name(runner.selection_name) == canonical_a
        ),
        None,
    )
    source_b = next(
        (
            runner
            for runner in snapshot.runners
            if normalize_market_player_name(runner.selection_name) == canonical_b
        ),
        None,
    )
    if source_a is None or source_b is None or source_a.selection_id == source_b.selection_id:
        raise RuntimeError("matched name pair could not be oriented into canonical A/B")

    join = HistoricalMarketJoin(
        join_hash=_join_hash(
            snapshot=snapshot,
            state=state,
            source_selection_a_id=source_a.selection_id,
            source_selection_b_id=source_b.selection_id,
            days_before=days_before_tournament_start,
            days_after=days_after_tournament_start,
        ),
        resolver_version=_JOIN_VERSION,
        source_market_id=snapshot.source_market_id,
        source_event_id=snapshot.source_event_id,
        source_market_time=snapshot.market_time,
        match_id=state.match_id,
        tour=state.tour,
        source_selection_a_id=source_a.selection_id,
        source_selection_b_id=source_b.selection_id,
        source_selection_a_name=source_a.selection_name,
        source_selection_b_name=source_b.selection_name,
        player_a_id=state.player_a_id,
        player_b_id=state.player_b_id,
        tournament_date_offset_days=offset_days,
        days_before_window=days_before_tournament_start,
        days_after_window=days_after_tournament_start,
    )
    return HistoricalMarketJoinResult(
        status="MATCHED",
        source_market_id=snapshot.source_market_id,
        source_event_id=snapshot.source_event_id,
        normalized_runner_names=normalized_names,
        candidate_match_ids=(state.match_id,),
        join=join,
    )
