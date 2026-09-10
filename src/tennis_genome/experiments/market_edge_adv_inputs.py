from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from tennis_genome.experiments.market_edge_adversarial import (
    MarketCoreSignalRow,
    SignalName,
    Tour,
)
from tennis_genome.experiments.market_edge_inputs import (
    ClosingMarketRow,
    SettledOutcome,
)


@dataclass(frozen=True)
class FrozenCoreSignalValue:
    match_id: str
    core_probability_a: float
    signal: float


def _required_probability(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 < result < 1.0:
        raise ValueError(f"{name} must be finite and in (0, 1)")
    return result


def _required_float(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _load_report(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("frozen model report must be a JSON object")
    return payload


def load_profile_gap_core_signal(
    path: str | Path,
    *,
    tour: Tour,
) -> dict[str, FrozenCoreSignalValue]:
    payload = _load_report(path)
    if payload.get("experiment_id") != "PROFILE-GAP-001":
        raise ValueError("unexpected Profile Gap experiment ID")
    if payload.get("tour") != tour:
        raise ValueError("Profile Gap report tour does not match requested tour")
    rows = payload.get("predictions", [])
    if not isinstance(rows, list):
        raise ValueError("Profile Gap predictions must be a list")
    result: dict[str, FrozenCoreSignalValue] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid Profile Gap prediction row")
        match_id = str(row["match_id"])
        if not match_id:
            raise ValueError("Profile Gap match_id must be non-empty")
        if match_id in result:
            raise ValueError("duplicate match_id in Profile Gap report")
        result[match_id] = FrozenCoreSignalValue(
            match_id=match_id,
            core_probability_a=_required_probability(
                row["strict_core_probability"],
                name="strict_core_probability",
            ),
            signal=_required_float(
                row["profile_gap_match"],
                name="profile_gap_match",
            ),
        )
    return result


def load_genome_core_signal(
    path: str | Path,
    *,
    tour: Tour,
) -> dict[str, FrozenCoreSignalValue]:
    payload = _load_report(path)
    if payload.get("experiment_id") != "GENOME-ADV-001":
        raise ValueError("unexpected Genome adversarial experiment ID")
    if payload.get("tour") != tour:
        raise ValueError("Genome report tour does not match requested tour")
    rows = payload.get("predictions", [])
    if not isinstance(rows, list):
        raise ValueError("Genome predictions must be a list")
    signal_field = "full_neighbor_residual" if tour == "ATP" else "core_neighbor_residual"
    result: dict[str, FrozenCoreSignalValue] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid Genome prediction row")
        match_id = str(row["match_id"])
        if not match_id:
            raise ValueError("Genome match_id must be non-empty")
        if match_id in result:
            raise ValueError("duplicate match_id in Genome report")
        result[match_id] = FrozenCoreSignalValue(
            match_id=match_id,
            core_probability_a=_required_probability(
                row["core_probability_a"],
                name="core_probability_a",
            ),
            signal=_required_float(row[signal_field], name=signal_field),
        )
    return result


def build_market_core_signal_rows(
    *,
    close_rows: dict[str, ClosingMarketRow],
    outcomes: dict[str, SettledOutcome],
    model_values: dict[str, FrozenCoreSignalValue],
    years_by_match: dict[str, int],
    tour: Tour,
    signal_name: SignalName,
) -> list[MarketCoreSignalRow]:
    if signal_name not in {"profile_gap", "genome"}:
        raise ValueError("unsupported signal_name")
    shared = sorted(set(close_rows).intersection(outcomes, model_values, years_by_match))
    rows: list[MarketCoreSignalRow] = []
    for match_id in shared:
        market = close_rows[match_id]
        if market.tour != tour:
            continue
        frozen = model_values[match_id]
        rows.append(
            MarketCoreSignalRow(
                match_id=match_id,
                tour=tour,
                year=int(years_by_match[match_id]),
                outcome_a=outcomes[match_id].outcome_a,
                market_probability_a=market.market_probability_a,
                core_probability_a=frozen.core_probability_a,
                signal=frozen.signal,
            )
        )
    return sorted(rows, key=lambda row: (row.year, row.match_id))
