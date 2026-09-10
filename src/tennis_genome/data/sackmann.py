from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path

import pandas as pd

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
    Surface,
    Tour,
)
from tennis_genome.data.identity import canonical_player_id, orient_pair

_SURFACES: dict[str, Surface] = {
    "hard": "Hard",
    "clay": "Clay",
    "grass": "Grass",
    "carpet": "Carpet",
}
_ENTRY_CODES = {"Q", "WC", "LL", "SE", "PR", "ALT"}


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "<na>"}:
        return None
    return int(float(text))


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "<na>"}:
        return None
    return float(text)


def _text(value: object, *, default: str = "") -> str:
    if value is None or pd.isna(value):
        return default
    return str(value).strip()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _seed_and_entry(
    seed_value: object,
    entry_value: object,
) -> tuple[int | None, str | None]:
    """Normalize numeric seed plus legacy entry codes stored in seed cells.

    Sackmann-style match files normally separate numeric seed from entry status,
    but some legacy WTA rows place recognized entry codes such as ``Q`` in the
    seed column. Explicit entry values take precedence. Unknown nonnumeric seed
    tokens remain fatal so source anomalies cannot be silently discarded.
    """
    entry = _optional_text(entry_value)
    seed_text = _text(seed_value)
    if not seed_text:
        return None, entry
    try:
        return int(float(seed_text)), entry
    except ValueError as exc:
        code = seed_text.upper()
        if code in _ENTRY_CODES:
            return None, entry or code
        raise ValueError(f"unrecognized nonnumeric seed token: {seed_text!r}") from exc


def _parse_tourney_date(value: object) -> date:
    raw = _text(value)
    if not raw:
        raise ValueError("tourney_date is required")
    if raw.endswith(".0"):
        raw = raw[:-2]
    return datetime.strptime(raw, "%Y%m%d").date()


def _surface(value: object) -> Surface:
    text = _text(value).casefold()
    return _SURFACES.get(text, "Unknown")


def _base_match_id(*, tour: Tour, row: pd.Series, source_order: object) -> str:
    tournament_id = _text(row.get("tourney_id"), default="unknown")
    match_num = _optional_int(row.get("match_num"))
    match_suffix = str(match_num) if match_num is not None else f"row-{source_order}"
    return f"{tour.lower()}:{tournament_id}:{match_suffix}"


def _disambiguate_match_id(
    base_match_id: str,
    *,
    round_name: str | None,
    player_a_id: str,
    player_b_id: str,
) -> str:
    """Disambiguate reused source match numbers using only pre-match-safe identity."""
    identity = "|".join((round_name or "", player_a_id, player_b_id))
    digest = sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{base_match_id}:d-{digest}"


def _oriented_int_pair(
    *,
    a_won: bool,
    winner_value: object,
    loser_value: object,
) -> tuple[int | None, int | None]:
    winner = _optional_int(winner_value)
    loser = _optional_int(loser_value)
    return (winner, loser) if a_won else (loser, winner)


def _oriented_float_pair(
    *,
    a_won: bool,
    winner_value: object,
    loser_value: object,
) -> tuple[float | None, float | None]:
    winner = _optional_float(winner_value)
    loser = _optional_float(loser_value)
    return (winner, loser) if a_won else (loser, winner)


def _oriented_text_pair(
    *,
    a_won: bool,
    winner_value: object,
    loser_value: object,
) -> tuple[str | None, str | None]:
    winner = _optional_text(winner_value)
    loser = _optional_text(loser_value)
    return (winner, loser) if a_won else (loser, winner)


def _match_stats(row: pd.Series, *, match_id: str, a_won: bool) -> MatchStats:
    aces_a, aces_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_ace"),
        loser_value=row.get("l_ace"),
    )
    df_a, df_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_df"),
        loser_value=row.get("l_df"),
    )
    svpt_a, svpt_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_svpt"),
        loser_value=row.get("l_svpt"),
    )
    first_in_a, first_in_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_1stIn"),
        loser_value=row.get("l_1stIn"),
    )
    first_won_a, first_won_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_1stWon"),
        loser_value=row.get("l_1stWon"),
    )
    second_won_a, second_won_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_2ndWon"),
        loser_value=row.get("l_2ndWon"),
    )
    sv_gms_a, sv_gms_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_SvGms"),
        loser_value=row.get("l_SvGms"),
    )
    bp_saved_a, bp_saved_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_bpSaved"),
        loser_value=row.get("l_bpSaved"),
    )
    bp_faced_a, bp_faced_b = _oriented_int_pair(
        a_won=a_won,
        winner_value=row.get("w_bpFaced"),
        loser_value=row.get("l_bpFaced"),
    )
    return MatchStats(
        match_id=match_id,
        aces_a=aces_a,
        aces_b=aces_b,
        double_faults_a=df_a,
        double_faults_b=df_b,
        service_points_a=svpt_a,
        service_points_b=svpt_b,
        first_serves_in_a=first_in_a,
        first_serves_in_b=first_in_b,
        first_serve_points_won_a=first_won_a,
        first_serve_points_won_b=first_won_b,
        second_serve_points_won_a=second_won_a,
        second_serve_points_won_b=second_won_b,
        service_games_a=sv_gms_a,
        service_games_b=sv_gms_b,
        break_points_saved_a=bp_saved_a,
        break_points_saved_b=bp_saved_b,
        break_points_faced_a=bp_faced_a,
        break_points_faced_b=bp_faced_b,
        duration_minutes=_optional_int(row.get("minutes")),
    )


def load_sackmann_csv(path: str | Path, *, tour: Tour) -> list[HistoricalMatch]:
    """Load one Jeff-Sackmann-style match CSV into the canonical contract."""
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

    base_ids = [
        _base_match_id(tour=tour, row=row, source_order=source_order)
        for source_order, row in frame.iterrows()
    ]
    base_id_counts = Counter(base_ids)

    matches: list[HistoricalMatch] = []
    for (source_order, row), base_match_id in zip(
        frame.iterrows(),
        base_ids,
        strict=True,
    ):
        winner_name = _text(row.get("winner_name"))
        loser_name = _text(row.get("loser_name"))
        if not winner_name or not loser_name:
            raise ValueError(f"row {source_order} has an empty winner/loser name")

        winner_id = canonical_player_id(
            tour=tour,
            source_id=row.get("winner_id"),
            name=winner_name,
        )
        loser_id = canonical_player_id(
            tour=tour,
            source_id=row.get("loser_id"),
            name=loser_name,
        )
        player_a_id, player_b_id, player_a_name, player_b_name, a_won = orient_pair(
            winner_id=winner_id,
            loser_id=loser_id,
            winner_name=winner_name,
            loser_name=loser_name,
        )

        tournament_id = _text(row.get("tourney_id"), default="unknown")
        round_name = _optional_text(row.get("round"))
        match_id = base_match_id
        if base_id_counts[base_match_id] > 1:
            match_id = _disambiguate_match_id(
                base_match_id,
                round_name=round_name,
                player_a_id=player_a_id,
                player_b_id=player_b_id,
            )

        rank_a, rank_b = _oriented_int_pair(
            a_won=a_won,
            winner_value=row.get("winner_rank"),
            loser_value=row.get("loser_rank"),
        )
        points_a, points_b = _oriented_int_pair(
            a_won=a_won,
            winner_value=row.get("winner_rank_points"),
            loser_value=row.get("loser_rank_points"),
        )
        winner_seed, winner_entry = _seed_and_entry(
            row.get("winner_seed"),
            row.get("winner_entry"),
        )
        loser_seed, loser_entry = _seed_and_entry(
            row.get("loser_seed"),
            row.get("loser_entry"),
        )
        if a_won:
            seed_a, seed_b = winner_seed, loser_seed
            entry_a, entry_b = winner_entry, loser_entry
        else:
            seed_a, seed_b = loser_seed, winner_seed
            entry_a, entry_b = loser_entry, winner_entry
        hand_a, hand_b = _oriented_text_pair(
            a_won=a_won,
            winner_value=row.get("winner_hand"),
            loser_value=row.get("loser_hand"),
        )
        height_a, height_b = _oriented_int_pair(
            a_won=a_won,
            winner_value=row.get("winner_ht"),
            loser_value=row.get("loser_ht"),
        )
        age_a, age_b = _oriented_float_pair(
            a_won=a_won,
            winner_value=row.get("winner_age"),
            loser_value=row.get("loser_age"),
        )
        ioc_a, ioc_b = _oriented_text_pair(
            a_won=a_won,
            winner_value=row.get("winner_ioc"),
            loser_value=row.get("loser_ioc"),
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
            round=round_name,
            best_of=_optional_int(row.get("best_of")),
            player_a_id=player_a_id,
            player_b_id=player_b_id,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
            rank_a=rank_a,
            rank_b=rank_b,
            rank_points_a=points_a,
            rank_points_b=points_b,
            draw_size=_optional_int(row.get("draw_size")),
            seed_a=seed_a,
            seed_b=seed_b,
            entry_a=entry_a,
            entry_b=entry_b,
            hand_a=hand_a,
            hand_b=hand_b,
            height_cm_a=height_a,
            height_cm_b=height_b,
            age_years_a=age_a,
            age_years_b=age_b,
            ioc_a=ioc_a,
            ioc_b=ioc_b,
        )
        outcome = MatchOutcome(
            match_id=match_id,
            a_won=a_won,
            score=score,
            retirement="RET" in score_upper,
            walkover="W/O" in score_upper or score_upper == "WO",
        )
        stats = _match_stats(row, match_id=match_id, a_won=a_won)
        matches.append(
            HistoricalMatch(
                pre_match=pre_match,
                outcome=outcome,
                stats=stats,
            )
        )

    return matches


def load_sackmann_csvs(
    paths: list[str | Path],
    *,
    tour: Tour,
) -> list[HistoricalMatch]:
    """Load a deterministic bundle of yearly/source CSVs."""
    resolved = sorted((Path(path).resolve() for path in paths), key=str)
    if not resolved:
        raise ValueError("at least one source CSV is required")

    matches: list[HistoricalMatch] = []
    next_order = 0
    for path in resolved:
        file_matches = load_sackmann_csv(path, tour=tour)
        for match in file_matches:
            state = replace(match.pre_match, source_order=next_order)
            matches.append(
                HistoricalMatch(
                    pre_match=state,
                    outcome=match.outcome,
                    stats=match.stats,
                )
            )
            next_order += 1

    return matches
