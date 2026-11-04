"""Fail-closed candidate history conversion for retained API-Tennis matches.

This is research infrastructure. A converted record is not an approved
production source or a prospective prediction. Caller-supplied identity and
tournament context must be reviewed independently of the provider fixture.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
    Surface,
)

from .api_tennis_enrichment import ApiTennisMatchEnrichment
from .api_tennis_matchstats_bridge import api_tennis_enrichment_to_match_stats


@dataclass(frozen=True)
class CandidateHistoryEvidence:
    match: HistoricalMatch
    raw_match_sha256: str
    source_observed_at: datetime
    source_manifest_sha256: str


def _reverse_stats(stats: MatchStats) -> MatchStats:
    source = asdict(stats)
    oriented: dict[str, object] = {"match_id": stats.match_id}
    for name, value in source.items():
        if name == "match_id":
            continue
        if name.endswith("_a"):
            oriented[name] = source[name[:-2] + "_b"]
        elif name.endswith("_b"):
            oriented[name] = source[name[:-2] + "_a"]
        else:
            oriented[name] = value
    return MatchStats(**oriented)


def build_candidate_historical_match(
    record: ApiTennisMatchEnrichment,
    *,
    reviewed_player_ids: Mapping[int, str],
    reviewed_surface: Surface,
    reviewed_tournament_level: str | None,
    reviewed_best_of: int,
    source_observed_at: datetime,
    target_cutoff_at: datetime,
    source_manifest_sha256: str,
) -> CandidateHistoryEvidence:
    """Convert one point-consistent prior match with explicit context.

    Source observation before the target does not establish that the provider's
    historical event date is an actual-start date. Same-date targets are refused.
    """
    if source_observed_at.tzinfo is None or source_observed_at.utcoffset() is None:
        raise ValueError("source observation must be timezone-aware")
    if target_cutoff_at.tzinfo is None or target_cutoff_at.utcoffset() is None:
        raise ValueError("target cutoff must be timezone-aware")
    event_date = date.fromisoformat(record.event_date)
    if event_date > source_observed_at.astimezone(UTC).date():
        raise ValueError("source cannot observe a finished match before its event date")
    if source_observed_at >= target_cutoff_at:
        raise ValueError("source was not observed before target cutoff")
    if event_date >= target_cutoff_at.astimezone(UTC).date():
        raise ValueError("historical match must precede target calendar date")
    if reviewed_surface not in {"Hard", "Clay", "Grass", "Carpet"}:
        raise ValueError("reviewed historical surface is required")
    if type(reviewed_best_of) is not int or reviewed_best_of not in {3, 5}:
        raise ValueError("reviewed best_of must be exactly 3 or 5")
    if record.tour == "WTA" and reviewed_best_of != 3:
        raise ValueError("WTA historical best_of must be 3")
    if len(source_manifest_sha256) != 64 or any(
        ch not in "0123456789abcdef" for ch in source_manifest_sha256
    ):
        raise ValueError("source manifest hash must be lowercase SHA-256")

    try:
        id_a = reviewed_player_ids[record.player_a_key]
        id_b = reviewed_player_ids[record.player_b_key]
    except KeyError as exc:
        raise ValueError("both player IDs require explicit reviewed crosswalks") from exc
    prefix = record.tour.lower() + ":"
    if not id_a.startswith(prefix) or not id_b.startswith(prefix) or id_a == id_b:
        raise ValueError("reviewed player IDs must be distinct and match the tour")

    stats = api_tennis_enrichment_to_match_stats(record)
    reverse = id_a > id_b
    match_id = f"api-tennis:{record.event_key}"
    pre_match = PreMatchState(
        match_id=match_id,
        tour=record.tour,
        event_date=event_date,
        source_order=record.event_key,
        tournament_id=f"api-tennis-tournament:{record.tournament_key}",
        tournament_name=record.tournament_name,
        tournament_level=reviewed_tournament_level,
        surface=reviewed_surface,
        round=record.tournament_round or None,
        best_of=reviewed_best_of,
        player_a_id=id_b if reverse else id_a,
        player_b_id=id_a if reverse else id_b,
        player_a_name=record.player_b_name if reverse else record.player_a_name,
        player_b_name=record.player_a_name if reverse else record.player_b_name,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
    )
    outcome = MatchOutcome(
        match_id=match_id,
        a_won=(record.winner_side == "B") if reverse else (record.winner_side == "A"),
        score=None,
        retirement=False,
        walkover=False,
    )
    return CandidateHistoryEvidence(
        match=HistoricalMatch(
            pre_match=pre_match,
            outcome=outcome,
            stats=_reverse_stats(stats) if reverse else stats,
        ),
        raw_match_sha256=record.raw_match_sha256,
        source_observed_at=source_observed_at,
        source_manifest_sha256=source_manifest_sha256,
    )
