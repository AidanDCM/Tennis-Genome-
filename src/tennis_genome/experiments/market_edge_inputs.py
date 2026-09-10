from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

import pandas as pd

from tennis_genome.experiments.market_edge import MarketSignalRow, SignalName, Tour
from tennis_genome.market.exchange_pricing import exchange_mid_implied_proportional_v1


@dataclass(frozen=True)
class ClosingMarketRow:
    match_id: str
    tour: Tour
    source_market_id: str
    market_probability_a: float
    market_probability_b: float
    best_back_a: float
    best_lay_a: float
    best_back_b: float
    best_lay_b: float
    published_at: str
    market_time: str
    market_total_matched: float | None
    market_base_rate: float | None
    record_hash: str
    join_hash: str


@dataclass(frozen=True)
class SettledOutcome:
    match_id: str
    outcome_a: bool


@dataclass(frozen=True)
class SignalValue:
    match_id: str
    signal: float


def _tour(value: object) -> Tour:
    text = str(value)
    if text not in {"ATP", "WTA"}:
        raise ValueError(f"invalid tour: {text}")
    return cast(Tour, text)


def _required_float(value: object, *, name: str) -> float:
    if value is None:
        raise ValueError(f"{name} is required")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _timestamp(value: object, *, name: str) -> datetime:
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed


def _sha256_text(value: object, *, name: str) -> str:
    text = str(value)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text.lower()):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")
    return text.lower()


def load_closing_market_rows(path: str | Path) -> dict[str, ClosingMarketRow]:
    """Load executable CLOSE_PREPLAY rows from a MARKET-HIST-001 artifact."""

    result: dict[str, ClosingMarketRow] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("join_status") != "MATCHED":
                continue
            join = record.get("join")
            if not isinstance(join, dict):
                raise ValueError(f"matched market lacks join at line {line_number}")
            checkpoints = [
                item
                for item in record.get("checkpoints", [])
                if item.get("checkpoint_name") == "CLOSE_PREPLAY"
            ]
            if not checkpoints:
                continue
            if len(checkpoints) != 1:
                raise ValueError(
                    f"multiple CLOSE_PREPLAY checkpoints at line {line_number}"
                )
            checkpoint = checkpoints[0]
            if checkpoint.get("data_package") not in {"ADVANCED", "PRO"}:
                continue
            if checkpoint.get("executable_two_way") is not True:
                continue

            seconds_to_start = _required_float(
                checkpoint.get("seconds_to_start"),
                name="seconds_to_start",
            )
            if seconds_to_start <= 0.0:
                raise ValueError("CLOSE_PREPLAY checkpoint is not strictly pre-match")
            published_text = str(checkpoint["published_at"])
            market_time_text = str(checkpoint["market_time"])
            published_at = _timestamp(published_text, name="published_at")
            market_time = _timestamp(market_time_text, name="market_time")
            actual_seconds_to_start = (market_time - published_at).total_seconds()
            if actual_seconds_to_start <= 0.0:
                raise ValueError("CLOSE_PREPLAY timestamp is not strictly before market time")
            if not math.isclose(
                actual_seconds_to_start,
                seconds_to_start,
                rel_tol=0.0,
                abs_tol=1e-3,
            ):
                raise ValueError("CLOSE_PREPLAY seconds_to_start disagrees with timestamps")

            match_id = str(join["match_id"])
            source_market_id = str(record["source_market_id"])
            if str(checkpoint.get("match_id")) != match_id:
                raise ValueError("CLOSE_PREPLAY match_id disagrees with join")
            if str(checkpoint.get("source_market_id")) != source_market_id:
                raise ValueError("CLOSE_PREPLAY source_market_id disagrees with market record")
            join_hash = _sha256_text(join.get("join_hash"), name="join.join_hash")
            checkpoint_join_hash = _sha256_text(
                checkpoint.get("join_hash"),
                name="checkpoint.join_hash",
            )
            if checkpoint_join_hash != join_hash:
                raise ValueError("CLOSE_PREPLAY join_hash disagrees with join")
            record_hash = _sha256_text(
                checkpoint.get("record_hash"),
                name="checkpoint.record_hash",
            )
            if match_id in result:
                raise ValueError(
                    f"multiple executable Betfair closing markets joined to {match_id}"
                )

            back_a = _required_float(checkpoint.get("best_back_a"), name="best_back_a")
            lay_a = _required_float(checkpoint.get("best_lay_a"), name="best_lay_a")
            back_b = _required_float(checkpoint.get("best_back_b"), name="best_back_b")
            lay_b = _required_float(checkpoint.get("best_lay_b"), name="best_lay_b")
            fair = exchange_mid_implied_proportional_v1(
                back_a=back_a,
                lay_a=lay_a,
                back_b=back_b,
                lay_b=lay_b,
            )
            result[match_id] = ClosingMarketRow(
                match_id=match_id,
                tour=_tour(join["tour"]),
                source_market_id=source_market_id,
                market_probability_a=fair.probability_a,
                market_probability_b=fair.probability_b,
                best_back_a=back_a,
                best_lay_a=lay_a,
                best_back_b=back_b,
                best_lay_b=lay_b,
                published_at=published_text,
                market_time=market_time_text,
                market_total_matched=(
                    None
                    if checkpoint.get("market_total_matched") is None
                    else _required_float(
                        checkpoint["market_total_matched"],
                        name="market_total_matched",
                    )
                ),
                market_base_rate=(
                    None
                    if checkpoint.get("market_base_rate") is None
                    else _required_float(
                        checkpoint["market_base_rate"],
                        name="market_base_rate",
                    )
                ),
                record_hash=record_hash,
                join_hash=join_hash,
            )
    return result


def load_settled_outcomes(path: str | Path) -> dict[str, SettledOutcome]:
    """Load completed, non-retirement, non-walkover outcomes for evaluation."""

    frame = pd.read_parquet(Path(path))
    required = {"match_id", "a_won", "retirement", "walkover"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"outcome table missing columns: {missing}")
    if frame["match_id"].astype(str).duplicated().any():
        raise ValueError("outcome table contains duplicate match_id values")
    result: dict[str, SettledOutcome] = {}
    for row in frame.itertuples(index=False):
        values = row._asdict()
        for field in ("a_won", "retirement", "walkover"):
            if pd.isna(values[field]):
                raise ValueError(f"outcome field {field} cannot be missing")
        if bool(values["walkover"]) or bool(values["retirement"]):
            continue
        match_id = str(values["match_id"])
        result[match_id] = SettledOutcome(
            match_id=match_id,
            outcome_a=bool(values["a_won"]),
        )
    return result


def _load_json_report(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("signal report must be a JSON object")
    return payload


def load_profile_gap_values(
    path: str | Path,
    *,
    tour: Tour,
) -> dict[str, SignalValue]:
    """Load only the frozen Profile Gap field; embedded report outcomes are ignored."""

    payload = _load_json_report(path)
    if payload.get("experiment_id") != "PROFILE-GAP-001":
        raise ValueError("unexpected Profile Gap experiment ID")
    if payload.get("tour") != tour:
        raise ValueError("Profile Gap report tour does not match requested tour")
    result: dict[str, SignalValue] = {}
    for row in payload.get("predictions", []):
        if not isinstance(row, dict):
            raise ValueError("invalid Profile Gap prediction row")
        match_id = str(row["match_id"])
        if match_id in result:
            raise ValueError("duplicate match_id in Profile Gap report")
        signal = _required_float(row["profile_gap_match"], name="profile_gap_match")
        result[match_id] = SignalValue(match_id=match_id, signal=signal)
    return result


def load_genome_values(
    path: str | Path,
    *,
    tour: Tour,
) -> dict[str, SignalValue]:
    """Load the tour-approved frozen GENOME-ADV residual field only."""

    payload = _load_json_report(path)
    if payload.get("experiment_id") != "GENOME-ADV-001":
        raise ValueError("unexpected Genome adversarial experiment ID")
    if payload.get("tour") != tour:
        raise ValueError("Genome report tour does not match requested tour")
    field = "full_neighbor_residual" if tour == "ATP" else "core_neighbor_residual"
    result: dict[str, SignalValue] = {}
    for row in payload.get("predictions", []):
        if not isinstance(row, dict):
            raise ValueError("invalid Genome prediction row")
        match_id = str(row["match_id"])
        if match_id in result:
            raise ValueError("duplicate match_id in Genome report")
        signal = _required_float(row[field], name=field)
        result[match_id] = SignalValue(match_id=match_id, signal=signal)
    return result


def build_market_signal_rows(
    *,
    close_rows: dict[str, ClosingMarketRow],
    outcomes: dict[str, SettledOutcome],
    signals: dict[str, SignalValue],
    years_by_match: dict[str, int],
    tour: Tour,
    signal_name: SignalName,
) -> list[MarketSignalRow]:
    """Intersect immutable market, signal and outcome ledgers on canonical match ID."""

    rows: list[MarketSignalRow] = []
    shared = sorted(set(close_rows).intersection(outcomes, signals, years_by_match))
    for match_id in shared:
        market = close_rows[match_id]
        if market.tour != tour:
            continue
        rows.append(
            MarketSignalRow(
                match_id=match_id,
                tour=tour,
                year=int(years_by_match[match_id]),
                outcome_a=outcomes[match_id].outcome_a,
                market_probability_a=market.market_probability_a,
                signal=signals[match_id].signal,
            )
        )
    return sorted(rows, key=lambda row: (row.year, row.match_id))


def load_match_years(pre_match_path: str | Path) -> dict[str, int]:
    """Load canonical source-date years without outcome access."""

    frame = pd.read_parquet(Path(pre_match_path), columns=["match_id", "event_date"])
    if frame["match_id"].astype(str).duplicated().any():
        raise ValueError("pre-match table contains duplicate match_id values")
    return {
        str(match_id): pd.Timestamp(event_date).year
        for match_id, event_date in zip(
            frame["match_id"],
            frame["event_date"],
            strict=True,
        )
    }
