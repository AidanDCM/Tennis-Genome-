"""Conservative offline bridge from retained Sportradar summaries to history.

This does not qualify a prospective prediction or authenticate a source receipt.
The caller supplies reviewed canonical identities, season surfaces and a T0
cutoff; no names are guessed and no absent player attributes are filled in.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
    Surface,
    Tour,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state import (
    _summary_stats,
    map_level,
    map_round,
)

# Match the existing frozen WTA live adapter's level semantics.
_WTA_LEVELS = {
    "grand_slam": "G",
    "wta_1000": "PM",
    "wta_500": "P",
    "wta_250": "I",
    "wta_championships": "F",
}


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Sportradar summary field must be an object")
    return value


def _text(value: object) -> str:
    return str(value if value is not None else "").strip()


def _aware_time(value: object) -> datetime:
    raw = _text(value)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("event start_time must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("event start_time must be timezone-aware")
    return parsed


def _swap_stats(stats: MatchStats) -> MatchStats:
    values = {field.name: getattr(stats, field.name) for field in fields(MatchStats)}
    for name in tuple(values):
        if name.endswith("_a"):
            partner = name[:-2] + "_b"
            values[name], values[partner] = values[partner], values[name]
    return MatchStats(**values)


def summary_to_historical_match(
    summary: dict[str, object],
    *,
    tour: Tour,
    crosswalk: dict[str, str],
    surfaces: dict[str, Surface],
    cutoff_at: datetime,
    source_observed_at: datetime,
    source_order: int,
) -> HistoricalMatch:
    """Convert one settled prior match; raise if any critical fact is absent.

    Conservative chronology excludes the whole current UTC day. A historical
    match's scheduled date is useful for ordering, but does not prove actual
    start for formal forward eligibility.
    """
    if cutoff_at.tzinfo is None or cutoff_at.utcoffset() is None:
        raise ValueError("cutoff_at must be timezone-aware")
    if source_observed_at.tzinfo is None or source_observed_at.utcoffset() is None:
        raise ValueError("source_observed_at must be timezone-aware")
    if source_observed_at > cutoff_at:
        raise ValueError("SOURCE_AFTER_CUTOFF")
    event = _object(summary.get("sport_event"))
    context = _object(event.get("sport_event_context"))
    category = _object(context.get("category"))
    expected_category = "sr:category:3" if tour == "ATP" else "sr:category:6"
    if _text(category.get("id")) != expected_category:
        raise ValueError("tour category does not match requested tour")
    competition = _object(context.get("competition"))
    if _text(competition.get("type")).lower() != "singles":
        raise ValueError("NOT_SINGLES")
    season = _object(context.get("season"))
    season_id = _text(season.get("id"))
    if not season_id or _text(season.get("competition_id")) != _text(competition.get("id")):
        raise ValueError("season/competition identity mismatch")
    surface = surfaces.get(season_id)
    if surface not in {"Hard", "Clay", "Grass", "Carpet", "Unknown"}:
        raise ValueError("MISSING_SURFACE")
    if event.get("start_time_confirmed") is not True or event.get("estimated") is True:
        raise ValueError("UNCONFIRMED_EVENT_TIME")
    start = _aware_time(event.get("start_time"))
    if start.astimezone(UTC).date() >= cutoff_at.astimezone(UTC).date():
        raise ValueError("NOT_PRIOR_TO_CUTOFF")
    status = _object(summary.get("sport_event_status"))
    if _text(status.get("status")).lower() not in {"closed", "ended"}:
        raise ValueError("NOT_COMPLETED")
    if _text(status.get("winning_reason")).lower() in {"walkover", "retirement", "defaulted"}:
        raise ValueError("WALKOVER_OR_RETIREMENT")
    competitors = event.get("competitors")
    if not isinstance(competitors, list) or len(competitors) != 2:
        raise ValueError("event requires exactly two competitors")
    by_side = {_text(_object(row).get("qualifier")): _object(row) for row in competitors}
    if set(by_side) != {"home", "away"}:
        raise ValueError("event requires one home and one away competitor")
    home, away = by_side["home"], by_side["away"]
    home_sr, away_sr = _text(home.get("id")), _text(away.get("id"))
    home_id, away_id = crosswalk.get(home_sr), crosswalk.get(away_sr)
    if not home_id or not away_id or home_id == away_id:
        raise ValueError("MISSING_IDENTITY")
    winner = _text(status.get("winner_id"))
    if winner not in {home_sr, away_sr}:
        raise ValueError("winner ID differs from competitors")
    match_id = _text(event.get("id"))
    if not match_id:
        raise ValueError("event ID is missing")
    round_raw = context.get("round")
    round_name = map_round(_object(round_raw).get("name")) if round_raw else None
    mode_raw = context.get("mode")
    best_of = _object(mode_raw).get("best_of") if mode_raw else None
    if best_of is not None and (type(best_of) is not int or best_of not in {3, 5}):
        raise ValueError("best_of must be 3 or 5")
    stats = _summary_stats(summary, match_id, expected_home_id=home_sr, expected_away_id=away_sr)
    a_is_home = home_id < away_id
    first, second = (home, away) if a_is_home else (away, home)
    raw_level = _text(competition.get("level")).lower()
    if tour == "ATP":
        level = map_level(raw_level)
    else:
        level = _WTA_LEVELS.get(raw_level)
        if raw_level and level is None:
            raise ValueError("unrecognized Sportradar WTA competition level")
    pre = PreMatchState(
        match_id=match_id,
        tour=tour,
        event_date=start.date(),
        source_order=source_order,
        tournament_id=season_id,
        tournament_name=_text(competition.get("name")),
        tournament_level=level,
        surface=surface,
        round=round_name,
        best_of=best_of,
        player_a_id=min(home_id, away_id),
        player_b_id=max(home_id, away_id),
        player_a_name=_text(first.get("name")),
        player_b_name=_text(second.get("name")),
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        seed_a=first.get("seed") if type(first.get("seed")) is int else None,
        seed_b=second.get("seed") if type(second.get("seed")) is int else None,
        ioc_a=_text(first.get("country_code")) or None,
        ioc_b=_text(second.get("country_code")) or None,
    )
    return HistoricalMatch(
        pre_match=pre,
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=(winner == home_sr) if a_is_home else (winner == away_sr),
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=stats if a_is_home or stats is None else _swap_stats(stats),
    )
