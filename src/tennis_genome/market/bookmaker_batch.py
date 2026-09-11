from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.market.bookmaker_manifest import (
    BookmakerSourceFile,
    BookmakerSourceManifest,
    load_bookmaker_source_manifest,
    verify_bookmaker_source_manifest,
)
from tennis_genome.market.canonical_market import load_market_pre_match_states
from tennis_genome.market.historical_join import normalize_market_player_name
from tennis_genome.market.odds import proportional_novig_two_way
from tennis_genome.market.providers.bookmaker_historical import (
    SanitizedBookmakerQuote,
    load_tennis_data_quotes,
    load_valuebetennis_quotes,
)

JoinStatus = Literal["MATCHED", "UNMATCHED", "AMBIGUOUS"]
StateIndex = dict[tuple[str, tuple[str, str]], tuple[PreMatchState, ...]]
_BATCH_VERSION = "market-book-001-batch-v1"
_RESOLVER_VERSION = "bookmaker-canonical-join-v1"
_MARKET_POLICY = "BOOKMAKER_CLOSE_V1"
_DAYS_BEFORE = 4
_DAYS_AFTER = 21


@dataclass(frozen=True)
class BookmakerJoin:
    join_hash: str
    resolver_version: str
    match_id: str
    tour: str
    player_a_id: str
    player_b_id: str
    player_a_name: str
    player_b_name: str
    source_match_date: str
    tournament_date_offset_days: int
    days_before_window: int
    days_after_window: int


@dataclass(frozen=True)
class BookmakerMarketSummary:
    batch_version: str
    market_policy: str
    bundle_sha256: str
    source_rows: int
    valid_quote_rows: int
    join_status_counts: dict[str, int]
    source_counts: dict[str, int]
    selected_primary_quotes: int
    selected_by_source: dict[str, int]
    source_conflict_rows: int
    overlap_matches: int
    output_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _pair_key(name_a: str, name_b: str) -> tuple[str, str]:
    normalized = (normalize_market_player_name(name_a), normalize_market_player_name(name_b))
    return tuple(sorted(normalized))  # type: ignore[return-value]


def _build_state_index(states: list[PreMatchState]) -> StateIndex:
    """Index canonical states by the exact frozen tour + unordered player-pair key."""

    buckets: dict[tuple[str, tuple[str, str]], list[PreMatchState]] = defaultdict(list)
    for state in states:
        buckets[(state.tour, _pair_key(state.player_a_name, state.player_b_name))].append(state)
    return {
        key: tuple(sorted(values, key=lambda state: (state.event_date, state.match_id)))
        for key, values in buckets.items()
    }


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


def _resolve_quote(
    quote: SanitizedBookmakerQuote,
    state_index: StateIndex,
) -> tuple[JoinStatus, tuple[str, ...], BookmakerJoin | None, float | None, float | None]:
    quote_pair = (quote.neutral_player_1_normalized, quote.neutral_player_2_normalized)
    indexed_states = state_index.get((quote.tour, quote_pair), ())
    candidates: list[tuple[PreMatchState, int]] = []
    for state in indexed_states:
        offset = (quote.match_date - state.event_date).days
        if -_DAYS_BEFORE <= offset <= _DAYS_AFTER:
            candidates.append((state, offset))
    candidate_ids = tuple(sorted(state.match_id for state, _ in candidates))
    if not candidates:
        return "UNMATCHED", (), None, None, None
    if len(candidates) != 1:
        return "AMBIGUOUS", candidate_ids, None, None, None

    state, offset = candidates[0]
    canonical_a = normalize_market_player_name(state.player_a_name)
    canonical_b = normalize_market_player_name(state.player_b_name)
    source = {
        quote.neutral_player_1_normalized: quote.decimal_odds_1,
        quote.neutral_player_2_normalized: quote.decimal_odds_2,
    }
    if canonical_a not in source or canonical_b not in source or canonical_a == canonical_b:
        raise RuntimeError("matched bookmaker pair could not be oriented into canonical A/B")
    join = BookmakerJoin(
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
    return "MATCHED", (state.match_id,), join, source[canonical_a], source[canonical_b]


def _roots(
    *,
    valuebet_root: str | Path,
    tennis_data_atp_root: str | Path,
    tennis_data_wta_root: str | Path,
) -> dict[str, Path]:
    return {
        "valuebetennis": Path(valuebet_root),
        "tennis_data_atp": Path(tennis_data_atp_root),
        "tennis_data_wta": Path(tennis_data_wta_root),
    }


def _load_manifest_file(
    item: BookmakerSourceFile,
    *,
    roots: dict[str, Path],
) -> list[SanitizedBookmakerQuote]:
    path = roots[item.root_key] / item.relative_path
    display_path = f"{item.root_key}/{item.relative_path}"
    if item.source_family == "VALUEBETENNIS":
        quotes = load_valuebetennis_quotes(
            path,
            source_file=display_path,
            source_file_sha256=item.sha256,
        )
    else:
        if item.tour not in {"ATP", "WTA"}:
            raise ValueError("Tennis-Data manifest item lacks valid tour")
        quotes = load_tennis_data_quotes(
            path,
            tour=item.tour,  # type: ignore[arg-type]
            source_file=display_path,
            source_file_sha256=item.sha256,
        )
    if len(quotes) != item.row_count:
        raise ValueError(f"bookmaker source row count changed after manifest: {display_path}")
    return quotes


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
        "neutral_player_names": [
            quote.neutral_player_1_name,
            quote.neutral_player_2_name,
        ],
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


def _quote_signature(record: dict[str, Any]) -> tuple[object, ...]:
    return (
        record["match_date"],
        record["decimal_odds_a"],
        record["decimal_odds_b"],
    )


def _select_primary(records: list[dict[str, Any]]) -> int:
    by_match_source: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if record["join_status"] != "MATCHED" or record["quote_valid"] is not True:
            continue
        join = record["join"]
        if not isinstance(join, dict):
            raise RuntimeError("matched bookmaker record lacks join")
        by_match_source[(str(join["match_id"]), str(record["source_family"]))].append(index)

    representative: dict[tuple[str, str], int] = {}
    for key, indices in by_match_source.items():
        signatures: dict[tuple[object, ...], list[int]] = defaultdict(list)
        for index in indices:
            signatures[_quote_signature(records[index])].append(index)
        if len(signatures) > 1:
            for index in indices:
                records[index]["source_conflict"] = True
            continue
        duplicate_indices = sorted(
            indices,
            key=lambda idx: str(records[idx]["sanitized_row_hash"]),
        )
        representative[key] = duplicate_indices[0]
        for duplicate_index in duplicate_indices[1:]:
            records[duplicate_index]["duplicate_of_sanitized_row_hash"] = records[
                duplicate_indices[0]
            ]["sanitized_row_hash"]

    matches = sorted({match_id for match_id, _ in representative})
    overlap_matches = 0
    for match_id in matches:
        valuebet = representative.get((match_id, "VALUEBETENNIS"))
        tennis_data = representative.get((match_id, "TENNIS_DATA_UK"))
        if valuebet is not None and tennis_data is not None:
            overlap_matches += 1
        selected = valuebet if valuebet is not None else tennis_data
        if selected is not None:
            records[selected]["selected_primary"] = True
            records[selected]["selected_policy"] = _MARKET_POLICY
    return overlap_matches


def _finalize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    for record in records:
        payload = dict(record)
        record_hash = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
        finalized.append({"record_hash": record_hash, **payload})
    return sorted(
        finalized,
        key=lambda item: (
            str(item["match_date"]),
            str(item["source_family"]),
            str(item["source_file"]),
            int(item["source_row_number"]),
            str(item["sanitized_row_hash"]),
        ),
    )


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
    state_index = _build_state_index(pre_match_states)
    start = date.fromisoformat(manifest.requested_start_date)
    end = date.fromisoformat(manifest.requested_end_date)
    records: list[dict[str, Any]] = []
    for item in manifest.files:
        for quote in _load_manifest_file(item, roots=roots):
            if not start <= quote.match_date <= end:
                raise ValueError("manifest-included bookmaker row is outside requested interval")
            status, candidates, join, odds_a, odds_b = _resolve_quote(quote, state_index)
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
        str(record["source_family"])
        for record in finalized
        if record["selected_primary"] is True
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


def write_market_book_records(records: list[dict[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def write_market_book_summary(summary: BookmakerMarketSummary, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build outcome-blind MARKET-BOOK-001 records")
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
