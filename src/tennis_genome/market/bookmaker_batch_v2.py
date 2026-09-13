from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.market.bookmaker_alias import tennis_data_orientation
from tennis_genome.market.bookmaker_batch import (
    BookmakerJoin,
    BookmakerMarketSummary,
    _canonical_json_bytes,
    _finalize_records,
    _load_manifest_file,
    _roots,
    _select_primary,
    write_market_book_records,
    write_market_book_summary,
)
from tennis_genome.market.bookmaker_manifest import (
    BookmakerSourceManifest,
    load_bookmaker_source_manifest,
    verify_bookmaker_source_manifest,
)
from tennis_genome.market.canonical_market import load_market_pre_match_states
from tennis_genome.market.historical_join import normalize_market_player_name
from tennis_genome.market.odds import proportional_novig_two_way
from tennis_genome.market.providers.bookmaker_historical import SanitizedBookmakerQuote

JoinStatus = Literal["MATCHED", "UNMATCHED", "AMBIGUOUS"]
StateIndex = dict[tuple[str, tuple[str, str]], tuple[PreMatchState, ...]]
DateIndex = dict[tuple[str, date], tuple[PreMatchState, ...]]
_BATCH_VERSION = "market-book-001-batch-v2"
_RESOLVER_VERSION = "bookmaker-canonical-join-v2"
_MARKET_POLICY = "BOOKMAKER_CLOSE_V1"
_DAYS_BEFORE = 4
_DAYS_AFTER = 21


def _pair_key(name_a: str, name_b: str) -> tuple[str, str]:
    return tuple(
        sorted(
            (
                normalize_market_player_name(name_a),
                normalize_market_player_name(name_b),
            )
        )
    )  # type: ignore[return-value]


def _build_state_indexes(
    states: list[PreMatchState],
) -> tuple[StateIndex, DateIndex]:
    pair_buckets: dict[tuple[str, tuple[str, str]], list[PreMatchState]] = defaultdict(list)
    date_buckets: dict[tuple[str, date], list[PreMatchState]] = defaultdict(list)
    for state in states:
        pair_buckets[(state.tour, _pair_key(state.player_a_name, state.player_b_name))].append(
            state
        )
        date_buckets[(state.tour, state.event_date)].append(state)
    pair_index = {
        key: tuple(sorted(values, key=lambda row: (row.event_date, row.match_id)))
        for key, values in pair_buckets.items()
    }
    date_index = {
        key: tuple(sorted(values, key=lambda row: row.match_id))
        for key, values in date_buckets.items()
    }
    return pair_index, date_index


def _join_hash(
    *,
    quote: SanitizedBookmakerQuote,
    state: PreMatchState,
    offset_days: int,
) -> str:
    payload = {
        "resolver_version": _RESOLVER_VERSION,
        "sanitized_row_hash": quote.sanitized_row_hash,
        "match_id": state.match_id,
        "player_a_id": state.player_a_id,
        "player_b_id": state.player_b_id,
        "offset_days": offset_days,
        "days_before": _DAYS_BEFORE,
        "days_after": _DAYS_AFTER,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _make_join(
    quote: SanitizedBookmakerQuote,
    state: PreMatchState,
    offset: int,
) -> BookmakerJoin:
    return BookmakerJoin(
        join_hash=_join_hash(quote=quote, state=state, offset_days=offset),
        resolver_version=_RESOLVER_VERSION,
        match_id=state.match_id,
        tour=state.tour,
        player_a_id=state.player_a_id,
        player_b_id=state.player_b_id,
        player_a_name=state.player_a_name,
        player_b_name=state.player_b_name,
        source_match_date=quote.match_date.isoformat(),
        tournament_date_offset_days=offset,
        days_before_window=_DAYS_BEFORE,
        days_after_window=_DAYS_AFTER,
    )


def _orient_exact(
    quote: SanitizedBookmakerQuote,
    state: PreMatchState,
) -> tuple[float | None, float | None]:
    canonical_a = normalize_market_player_name(state.player_a_name)
    canonical_b = normalize_market_player_name(state.player_b_name)
    source = {
        quote.neutral_player_1_normalized: quote.decimal_odds_1,
        quote.neutral_player_2_normalized: quote.decimal_odds_2,
    }
    if canonical_a not in source or canonical_b not in source or canonical_a == canonical_b:
        raise RuntimeError("matched bookmaker pair could not be oriented into canonical A/B")
    return source[canonical_a], source[canonical_b]


def _resolve_exact(
    quote: SanitizedBookmakerQuote,
    pair_index: StateIndex,
) -> tuple[JoinStatus, tuple[str, ...], BookmakerJoin | None, float | None, float | None]:
    pair = (quote.neutral_player_1_normalized, quote.neutral_player_2_normalized)
    candidates: list[tuple[PreMatchState, int]] = []
    for state in pair_index.get((quote.tour, pair), ()):
        offset = (quote.match_date - state.event_date).days
        if -_DAYS_BEFORE <= offset <= _DAYS_AFTER:
            candidates.append((state, offset))
    candidate_ids = tuple(sorted(state.match_id for state, _ in candidates))
    if not candidates:
        return "UNMATCHED", (), None, None, None
    if len(candidates) != 1:
        return "AMBIGUOUS", candidate_ids, None, None, None
    state, offset = candidates[0]
    odds_a, odds_b = _orient_exact(quote, state)
    return "MATCHED", (state.match_id,), _make_join(quote, state, offset), odds_a, odds_b


def _date_candidates(
    quote: SanitizedBookmakerQuote,
    date_index: DateIndex,
) -> tuple[PreMatchState, ...]:
    rows: list[PreMatchState] = []
    first_date = quote.match_date - timedelta(days=_DAYS_AFTER)
    last_date = quote.match_date + timedelta(days=_DAYS_BEFORE)
    current = first_date
    while current <= last_date:
        rows.extend(date_index.get((quote.tour, current), ()))
        current += timedelta(days=1)
    return tuple(rows)


def _resolve_tennis_data_alias(
    quote: SanitizedBookmakerQuote,
    date_index: DateIndex,
) -> tuple[JoinStatus, tuple[str, ...], BookmakerJoin | None, float | None, float | None]:
    candidates: list[tuple[PreMatchState, int, int]] = []
    ambiguous_orientation_ids: set[str] = set()
    for state in _date_candidates(quote, date_index):
        offset = (quote.match_date - state.event_date).days
        orientations = tennis_data_orientation(
            quote.neutral_player_1_name,
            quote.neutral_player_2_name,
            state.player_a_name,
            state.player_b_name,
        )
        if len(orientations) > 1:
            ambiguous_orientation_ids.add(state.match_id)
        elif len(orientations) == 1:
            candidates.append((state, offset, orientations[0]))

    candidate_ids = tuple(
        sorted({state.match_id for state, _, _ in candidates} | ambiguous_orientation_ids)
    )
    if ambiguous_orientation_ids:
        return "AMBIGUOUS", candidate_ids, None, None, None
    if not candidates:
        return "UNMATCHED", (), None, None, None
    if len(candidates) != 1:
        return "AMBIGUOUS", candidate_ids, None, None, None

    state, offset, orientation = candidates[0]
    if orientation == 1:
        odds_a, odds_b = quote.decimal_odds_1, quote.decimal_odds_2
    elif orientation == -1:
        odds_a, odds_b = quote.decimal_odds_2, quote.decimal_odds_1
    else:
        raise RuntimeError("invalid Tennis-Data alias orientation")
    return "MATCHED", (state.match_id,), _make_join(quote, state, offset), odds_a, odds_b


def _resolve_quote(
    quote: SanitizedBookmakerQuote,
    pair_index: StateIndex,
    date_index: DateIndex,
) -> tuple[JoinStatus, tuple[str, ...], BookmakerJoin | None, float | None, float | None]:
    exact = _resolve_exact(quote, pair_index)
    if exact[0] != "UNMATCHED" or quote.source_family != "TENNIS_DATA_UK":
        return exact
    return _resolve_tennis_data_alias(quote, date_index)


def _base_record(
    quote: SanitizedBookmakerQuote,
    *,
    status: JoinStatus,
    candidates: tuple[str, ...],
    join: BookmakerJoin | None,
    odds_a: float | None,
    odds_b: float | None,
) -> dict[str, Any]:
    probability_a: float | None = None
    probability_b: float | None = None
    implied_sum: float | None = None
    overround: float | None = None
    if quote.quote_valid and odds_a is not None and odds_b is not None:
        probability_a, probability_b = proportional_novig_two_way(odds_a, odds_b)
        implied_sum = (1.0 / odds_a) + (1.0 / odds_b)
        overround = implied_sum - 1.0
    return {
        "batch_version": _BATCH_VERSION,
        "market_policy": _MARKET_POLICY,
        "source_family": quote.source_family,
        "source_file": quote.source_file,
        "source_file_sha256": quote.source_file_sha256,
        "source_row_number": quote.source_row_number,
        "source_row_key": quote.source_row_key,
        "sanitized_row_hash": quote.sanitized_row_hash,
        "match_date": quote.match_date.isoformat(),
        "tour": quote.tour,
        "neutral_player_names": [quote.neutral_player_1_name, quote.neutral_player_2_name],
        "neutral_player_names_normalized": [
            quote.neutral_player_1_normalized,
            quote.neutral_player_2_normalized,
        ],
        "quote_valid": quote.quote_valid,
        "join_status": status,
        "candidate_match_ids": list(candidates),
        "join": None if join is None else asdict(join),
        "decimal_odds_a": odds_a,
        "decimal_odds_b": odds_b,
        "raw_implied_probability_sum": implied_sum,
        "overround": overround,
        "market_probability_a": probability_a,
        "market_probability_b": probability_b,
        "source_conflict": False,
        "duplicate_of_sanitized_row_hash": None,
        "selected_primary": False,
        "selected_policy": None,
    }


def build_market_book_records(
    *,
    manifest: BookmakerSourceManifest,
    pre_match_states: list[PreMatchState],
    valuebet_root: str | Path,
    tennis_data_atp_root: str | Path,
    tennis_data_wta_root: str | Path,
) -> tuple[list[dict[str, Any]], BookmakerMarketSummary]:
    roots = _roots(
        valuebet_root=valuebet_root,
        tennis_data_atp_root=tennis_data_atp_root,
        tennis_data_wta_root=tennis_data_wta_root,
    )
    pair_index, date_index = _build_state_indexes(pre_match_states)
    start = date.fromisoformat(manifest.requested_start_date)
    end = date.fromisoformat(manifest.requested_end_date)
    records: list[dict[str, Any]] = []
    for item in manifest.files:
        for quote in _load_manifest_file(item, roots=roots):
            if not start <= quote.match_date <= end:
                raise ValueError("manifest-included bookmaker row is outside requested interval")
            status, candidates, join, odds_a, odds_b = _resolve_quote(quote, pair_index, date_index)
            records.append(
                _base_record(
                    quote,
                    status=status,
                    candidates=candidates,
                    join=join,
                    odds_a=odds_a,
                    odds_b=odds_b,
                )
            )

    overlap_matches = _select_primary(records)
    finalized = _finalize_records(records)
    output_hash = hashlib.sha256(
        b"\n".join(_canonical_json_bytes(record) for record in finalized)
    ).hexdigest()
    join_counts = Counter(str(record["join_status"]) for record in finalized)
    source_counts = Counter(str(record["source_family"]) for record in finalized)
    selected_counts = Counter(
        str(record["source_family"]) for record in finalized if record["selected_primary"] is True
    )
    summary = BookmakerMarketSummary(
        batch_version=_BATCH_VERSION,
        market_policy=_MARKET_POLICY,
        bundle_sha256=manifest.bundle_sha256,
        source_rows=len(finalized),
        valid_quote_rows=sum(record["quote_valid"] is True for record in finalized),
        join_status_counts=dict(sorted(join_counts.items())),
        source_counts=dict(sorted(source_counts.items())),
        selected_primary_quotes=sum(record["selected_primary"] is True for record in finalized),
        selected_by_source=dict(sorted(selected_counts.items())),
        source_conflict_rows=sum(record["source_conflict"] is True for record in finalized),
        overlap_matches=overlap_matches,
        output_sha256=output_hash,
    )
    return finalized, summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build outcome-blind MARKET-BOOK-001 v2 records")
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--valuebet-root", required=True, type=Path)
    parser.add_argument("--tennis-data-atp-root", required=True, type=Path)
    parser.add_argument("--tennis-data-wta-root", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = load_bookmaker_source_manifest(args.source_manifest)
    verify_bookmaker_source_manifest(
        manifest,
        valuebet_root=args.valuebet_root,
        tennis_data_atp_root=args.tennis_data_atp_root,
        tennis_data_wta_root=args.tennis_data_wta_root,
    )
    states = load_market_pre_match_states(args.pre_match)
    records, summary = build_market_book_records(
        manifest=manifest,
        pre_match_states=states,
        valuebet_root=args.valuebet_root,
        tennis_data_atp_root=args.tennis_data_atp_root,
        tennis_data_wta_root=args.tennis_data_wta_root,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_market_book_records(records, args.output_dir / "market_book_001_records.jsonl")
    write_market_book_summary(summary, args.output_dir / "market_book_001_summary.json")
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
