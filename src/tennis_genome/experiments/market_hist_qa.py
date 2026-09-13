from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from tennis_genome.experiments.market_edge_inputs import load_closing_market_rows
from tennis_genome.market.historical_manifest import (
    HistoricalSourceManifest,
    load_historical_source_manifest,
    verify_historical_source_manifest,
)

Tour = Literal["ATP", "WTA"]
TourStatus = Literal[
    "ELIGIBLE_CONFIRMATORY",
    "EXPLORATORY_ONLY_COVERAGE",
    "BLOCKED_STRUCTURAL",
]
OverallStatus = Literal[
    "ELIGIBLE_CONFIRMATORY",
    "PARTIAL_TOUR_ELIGIBILITY",
    "EXPLORATORY_ONLY_COVERAGE",
    "BLOCKED_STRUCTURAL",
]
_EXPERIMENT_ID = "MARKET-HIST-QA-001"
_DEVELOPMENT_END = date(2025, 12, 31)
_END_BUFFER_DAYS = 21
_MIN_OVERALL_COVERAGE = 0.60
_MIN_RECENT_COVERAGE = 0.50
_MIN_RECENT_ROWS = 100
_MIN_PRIOR_ROWS = 1000
_MIN_EVALUATION_YEARS = 5
_RECENT_YEARS = (2021, 2022, 2023, 2024, 2025)
_CHECKPOINTS = ("T-24H", "T-6H", "T-1H", "T-15M", "CLOSE_PREPLAY")


@dataclass(frozen=True)
class NumericSummary:
    n: int
    minimum: float | None
    p10: float | None
    median: float | None
    p90: float | None
    maximum: float | None
    mean: float | None


@dataclass(frozen=True)
class AnnualCoverage:
    year: int
    eligible_canonical: int
    identity_matched: int
    executable_close: int
    close_coverage: float | None


@dataclass(frozen=True)
class GroupCoverage:
    dimension: str
    value: str
    eligible_canonical: int
    executable_close: int
    close_coverage: float | None


@dataclass(frozen=True)
class CoverageGates:
    overall_close_coverage_at_least_60pct: bool
    every_recent_year_close_coverage_at_least_50pct: bool
    every_recent_year_at_least_100_rows: bool
    at_least_1000_prior_rows_before_first_evaluation_year: bool
    at_least_five_evaluation_years: bool
    all_2021_2025_years_in_evaluation_population: bool
    passed: bool


@dataclass(frozen=True)
class TourQA:
    tour: Tour
    status: TourStatus
    eligible_canonical: int
    identity_matched: int
    executable_close: int
    overall_close_coverage: float | None
    first_confirmatory_evaluation_year: int | None
    confirmatory_evaluation_years: tuple[int, ...]
    prior_rows_before_first_evaluation_year: int
    annual: tuple[AnnualCoverage, ...]
    group_coverage: tuple[GroupCoverage, ...]
    gates: CoverageGates


@dataclass(frozen=True)
class MarketHistQAReport:
    experiment_id: str
    overall_status: OverallStatus
    structural_pass: bool
    structural_errors: tuple[str, ...]
    bundle_sha256: str | None
    data_package: str | None
    requested_start_date: str | None
    requested_end_date: str | None
    denominator_start_date: str | None
    denominator_end_date: str | None
    source_market_records: int
    source_join_status_counts: dict[str, int]
    checkpoint_counts: dict[str, int]
    executable_checkpoint_counts: dict[str, int]
    close_quote_seconds_to_start: NumericSummary
    implied_probability_spread: NumericSummary
    decimal_price_spread: NumericSummary
    market_total_matched: NumericSummary
    market_base_rate_available_fraction: float | None
    tours: tuple[TourQA, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _numeric_summary(values: list[float]) -> NumericSummary:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if finite.size == 0:
        return NumericSummary(0, None, None, None, None, None, None)
    return NumericSummary(
        n=int(finite.size),
        minimum=float(np.min(finite)),
        p10=float(np.quantile(finite, 0.10)),
        median=float(np.median(finite)),
        p90=float(np.quantile(finite, 0.90)),
        maximum=float(np.max(finite)),
        mean=float(np.mean(finite)),
    )


def _load_records(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
                continue
            if not isinstance(value, dict):
                errors.append(f"line {line_number}: record is not a JSON object")
                continue
            records.append(value)
    if not records:
        errors.append("MARKET-HIST artifact contains no market records")
    return records, errors


def _manifest_file_map(manifest: HistoricalSourceManifest) -> dict[str, str]:
    return {item.relative_path: item.sha256 for item in manifest.files}


def _record_structural_checks(
    records: list[dict[str, Any]],
    *,
    manifest: HistoricalSourceManifest,
) -> list[str]:
    errors: list[str] = []
    source_files = _manifest_file_map(manifest)
    seen_market_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        market_id = str(record.get("source_market_id", ""))
        if not market_id:
            errors.append(f"record {index}: missing source_market_id")
        elif market_id in seen_market_ids:
            errors.append(f"record {index}: duplicate source_market_id {market_id}")
        else:
            seen_market_ids.add(market_id)

        source_file = str(record.get("source_file", ""))
        source_hash = str(record.get("source_file_sha256", "")).lower()
        if source_file not in source_files:
            errors.append(f"record {index}: source_file is not in bundle manifest")
        elif source_hash != source_files[source_file]:
            errors.append(f"record {index}: source_file_sha256 disagrees with bundle manifest")

        package = str(record.get("data_package", ""))
        if package != manifest.data_package:
            errors.append(f"record {index}: data_package disagrees with source manifest")

        join_status = str(record.get("join_status", ""))
        if join_status not in {"MATCHED", "UNMATCHED", "AMBIGUOUS"}:
            errors.append(f"record {index}: invalid join_status {join_status!r}")
        if join_status == "MATCHED" and not isinstance(record.get("join"), dict):
            errors.append(f"record {index}: MATCHED record lacks join object")

        checkpoints = record.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            errors.append(f"record {index}: checkpoints is not a list")
            continue
        for checkpoint in checkpoints:
            if not isinstance(checkpoint, dict):
                errors.append(f"record {index}: checkpoint is not a JSON object")
                continue
            if checkpoint.get("data_package") != manifest.data_package:
                errors.append(f"record {index}: checkpoint package disagrees with manifest")
            if str(checkpoint.get("source_file_sha256", "")).lower() != source_hash:
                errors.append(f"record {index}: checkpoint source hash disagrees with record")
    return errors


def _load_canonical(
    pre_match_path: str | Path,
    outcomes_path: str | Path,
) -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    required_pre = {
        "match_id",
        "tour",
        "event_date",
        "tournament_level",
        "surface",
        "round",
        "rank_a",
        "rank_b",
    }
    required_outcomes = {"match_id", "retirement", "walkover"}
    pre = pd.read_parquet(Path(pre_match_path))
    outcomes = pd.read_parquet(Path(outcomes_path))
    missing_pre = sorted(required_pre.difference(pre.columns))
    missing_outcomes = sorted(required_outcomes.difference(outcomes.columns))
    if missing_pre:
        errors.append(f"pre-match table missing columns: {missing_pre}")
    if missing_outcomes:
        errors.append(f"outcome table missing columns: {missing_outcomes}")
    if errors:
        return pd.DataFrame(), errors

    pre = pre.copy()
    outcomes = outcomes.copy()
    pre["match_id"] = pre["match_id"].astype(str)
    outcomes["match_id"] = outcomes["match_id"].astype(str)
    if pre["match_id"].duplicated().any():
        errors.append("pre-match table contains duplicate match_id values")
    if outcomes["match_id"].duplicated().any():
        errors.append("outcome table contains duplicate match_id values")
    if errors:
        return pd.DataFrame(), errors

    if set(pre["match_id"]) != set(outcomes["match_id"]):
        errors.append("canonical pre-match/outcome match-id sets differ")
        return pd.DataFrame(), errors
    pre["event_date"] = pd.to_datetime(pre["event_date"]).dt.date
    if any(value > _DEVELOPMENT_END for value in pre["event_date"]):
        errors.append("canonical QA input contains post-2025 data")
    merged = pre.merge(
        outcomes[["match_id", "retirement", "walkover"]],
        on="match_id",
        how="inner",
        validate="one_to_one",
    )
    if merged[["retirement", "walkover"]].isna().any().any():
        errors.append("canonical retirement/walkover flags contain missing values")
    return merged, errors


def _rank_band(rank_a: object, rank_b: object) -> str:
    if pd.isna(rank_a) or pd.isna(rank_b):
        return "rank_missing"
    worst = max(int(rank_a), int(rank_b))
    if worst <= 20:
        return "both_top_20"
    if worst <= 50:
        return "both_top_50"
    if worst <= 100:
        return "both_top_100"
    return "outside_top_100"


def _group_coverage(
    eligible: pd.DataFrame,
    close_ids: set[str],
) -> tuple[GroupCoverage, ...]:
    if eligible.empty:
        return ()
    frame = eligible.copy()
    frame["covered"] = frame["match_id"].isin(close_ids)
    frame["rank_band"] = [
        _rank_band(a, b) for a, b in zip(frame["rank_a"], frame["rank_b"], strict=True)
    ]
    dimensions = (
        ("surface", "surface"),
        ("tournament_level", "tournament_level"),
        ("round", "round"),
        ("rank_band", "rank_band"),
    )
    rows: list[GroupCoverage] = []
    for dimension, column in dimensions:
        values = frame[column].fillna("<MISSING>").astype(str)
        for value in sorted(values.unique()):
            mask = values == value
            total = int(mask.sum())
            covered = int(frame.loc[mask, "covered"].sum())
            rows.append(
                GroupCoverage(
                    dimension=dimension,
                    value=value,
                    eligible_canonical=total,
                    executable_close=covered,
                    close_coverage=(covered / total) if total else None,
                )
            )
    return tuple(rows)


def _tour_qa(
    canonical: pd.DataFrame,
    *,
    tour: Tour,
    matched_ids: set[str],
    close_ids: set[str],
    start: date,
    end: date,
) -> TourQA:
    interior_end = end - timedelta(days=_END_BUFFER_DAYS)
    eligible = canonical[
        (canonical["tour"].astype(str) == tour)
        & (canonical["event_date"] >= start)
        & (canonical["event_date"] <= interior_end)
        & (~canonical["retirement"].astype(bool))
        & (~canonical["walkover"].astype(bool))
    ].copy()
    eligible_ids = set(eligible["match_id"].astype(str))
    matched = eligible_ids.intersection(matched_ids)
    covered = eligible_ids.intersection(close_ids)
    overall = (len(covered) / len(eligible_ids)) if eligible_ids else None

    years = sorted(set(int(value.year) for value in eligible["event_date"]))
    annual: list[AnnualCoverage] = []
    close_counts_by_year: dict[int, int] = {}
    for year in years:
        year_frame = eligible[eligible["event_date"].map(lambda value: value.year) == year]
        year_ids = set(year_frame["match_id"].astype(str))
        year_matched = len(year_ids.intersection(matched_ids))
        year_close = len(year_ids.intersection(close_ids))
        close_counts_by_year[year] = year_close
        annual.append(
            AnnualCoverage(
                year=year,
                eligible_canonical=len(year_ids),
                identity_matched=year_matched,
                executable_close=year_close,
                close_coverage=(year_close / len(year_ids)) if year_ids else None,
            )
        )

    first_eval: int | None = None
    prior_rows = 0
    for year in years:
        if prior_rows >= _MIN_PRIOR_ROWS and close_counts_by_year.get(year, 0) > 0:
            first_eval = year
            break
        prior_rows += close_counts_by_year.get(year, 0)
    if first_eval is None:
        evaluation_years: tuple[int, ...] = ()
        prior_before_first = prior_rows
    else:
        evaluation_years = tuple(
            year for year in years if year >= first_eval and close_counts_by_year.get(year, 0) > 0
        )
        prior_before_first = sum(
            count for year, count in close_counts_by_year.items() if year < first_eval
        )

    annual_by_year = {row.year: row for row in annual}
    recent_coverage_ok = all(
        year in annual_by_year
        and annual_by_year[year].close_coverage is not None
        and cast(float, annual_by_year[year].close_coverage) >= _MIN_RECENT_COVERAGE
        for year in _RECENT_YEARS
    )
    recent_rows_ok = all(
        year in annual_by_year and annual_by_year[year].executable_close >= _MIN_RECENT_ROWS
        for year in _RECENT_YEARS
    )
    all_recent_eval = all(year in evaluation_years for year in _RECENT_YEARS)
    gate_values = {
        "overall": overall is not None and overall >= _MIN_OVERALL_COVERAGE,
        "recent_coverage": recent_coverage_ok,
        "recent_rows": recent_rows_ok,
        "prior": first_eval is not None and prior_before_first >= _MIN_PRIOR_ROWS,
        "years": len(evaluation_years) >= _MIN_EVALUATION_YEARS,
        "recent_eval": all_recent_eval,
    }
    passed = all(gate_values.values())
    gates = CoverageGates(
        overall_close_coverage_at_least_60pct=gate_values["overall"],
        every_recent_year_close_coverage_at_least_50pct=gate_values["recent_coverage"],
        every_recent_year_at_least_100_rows=gate_values["recent_rows"],
        at_least_1000_prior_rows_before_first_evaluation_year=gate_values["prior"],
        at_least_five_evaluation_years=gate_values["years"],
        all_2021_2025_years_in_evaluation_population=gate_values["recent_eval"],
        passed=passed,
    )
    return TourQA(
        tour=tour,
        status="ELIGIBLE_CONFIRMATORY" if passed else "EXPLORATORY_ONLY_COVERAGE",
        eligible_canonical=len(eligible_ids),
        identity_matched=len(matched),
        executable_close=len(covered),
        overall_close_coverage=overall,
        first_confirmatory_evaluation_year=first_eval,
        confirmatory_evaluation_years=evaluation_years,
        prior_rows_before_first_evaluation_year=prior_before_first,
        annual=tuple(annual),
        group_coverage=_group_coverage(eligible, close_ids),
        gates=gates,
    )


def _blocked_report(
    errors: list[str],
    manifest: HistoricalSourceManifest | None,
) -> MarketHistQAReport:
    return MarketHistQAReport(
        experiment_id=_EXPERIMENT_ID,
        overall_status="BLOCKED_STRUCTURAL",
        structural_pass=False,
        structural_errors=tuple(sorted(set(errors))),
        bundle_sha256=None if manifest is None else manifest.bundle_sha256,
        data_package=None if manifest is None else manifest.data_package,
        requested_start_date=None if manifest is None else manifest.requested_start_date,
        requested_end_date=None if manifest is None else manifest.requested_end_date,
        denominator_start_date=None if manifest is None else manifest.requested_start_date,
        denominator_end_date=(
            None
            if manifest is None
            else (
                date.fromisoformat(manifest.requested_end_date) - timedelta(days=_END_BUFFER_DAYS)
            ).isoformat()
        ),
        source_market_records=0,
        source_join_status_counts={},
        checkpoint_counts={},
        executable_checkpoint_counts={},
        close_quote_seconds_to_start=_numeric_summary([]),
        implied_probability_spread=_numeric_summary([]),
        decimal_price_spread=_numeric_summary([]),
        market_total_matched=_numeric_summary([]),
        market_base_rate_available_fraction=None,
        tours=(),
    )


def run_market_hist_qa(
    *,
    source_manifest_path: str | Path,
    market_hist_records_path: str | Path,
    pre_match_path: str | Path,
    outcomes_path: str | Path,
    source_root: str | Path | None = None,
) -> MarketHistQAReport:
    errors: list[str] = []
    manifest: HistoricalSourceManifest | None = None
    try:
        manifest = load_historical_source_manifest(source_manifest_path)
        if source_root is not None:
            verify_historical_source_manifest(manifest, root=source_root)
    except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        return _blocked_report([f"source manifest verification failed: {exc}"], manifest)

    start = date.fromisoformat(manifest.requested_start_date)
    end = date.fromisoformat(manifest.requested_end_date)
    interior_end = end - timedelta(days=_END_BUFFER_DAYS)
    if interior_end < start:
        errors.append("declared source interval is too short for boundary-safe coverage")

    records, record_errors = _load_records(market_hist_records_path)
    errors.extend(record_errors)
    errors.extend(_record_structural_checks(records, manifest=manifest))

    canonical, canonical_errors = _load_canonical(pre_match_path, outcomes_path)
    errors.extend(canonical_errors)

    close_rows: dict[str, Any] = {}
    try:
        close_rows = load_closing_market_rows(market_hist_records_path)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"executable close validation failed: {exc}")

    if errors:
        blocked = _blocked_report(errors, manifest)
        return replace(blocked, source_market_records=len(records))

    canonical_by_id = canonical.set_index("match_id", drop=False)
    matched_ids: set[str] = set()
    join_status_counts: Counter[str] = Counter()
    checkpoint_counts: Counter[str] = Counter()
    executable_counts: Counter[str] = Counter()
    quote_ages: list[float] = []
    probability_spreads: list[float] = []
    price_spreads: list[float] = []
    total_matched: list[float] = []
    base_rate_total = 0
    base_rate_available = 0

    for record in records:
        status = str(record["join_status"])
        join_status_counts[status] += 1
        if status == "MATCHED":
            join = cast(dict[str, Any], record["join"])
            match_id = str(join["match_id"])
            if match_id not in canonical_by_id.index:
                errors.append(
                    f"matched Betfair market points to unknown canonical match {match_id}"
                )
            else:
                canonical_tour = str(canonical_by_id.loc[match_id, "tour"])
                if str(join.get("tour")) != canonical_tour:
                    errors.append(f"matched Betfair market tour disagrees for {match_id}")
                matched_ids.add(match_id)
        checkpoints = record.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            errors.append("MARKET-HIST record checkpoints must be a list")
            continue
        for checkpoint in checkpoints:
            name = str(checkpoint.get("checkpoint_name", ""))
            if name in _CHECKPOINTS:
                checkpoint_counts[name] += 1
                if checkpoint.get("executable_two_way") is True:
                    executable_counts[name] += 1
            if name == "CLOSE_PREPLAY" and checkpoint.get("executable_two_way") is True:
                seconds = float(checkpoint["seconds_to_start"])
                quote_ages.append(seconds)
                back_a = float(checkpoint["best_back_a"])
                lay_a = float(checkpoint["best_lay_a"])
                back_b = float(checkpoint["best_back_b"])
                lay_b = float(checkpoint["best_lay_b"])
                probability_spreads.extend(
                    [
                        (1.0 / back_a) - (1.0 / lay_a),
                        (1.0 / back_b) - (1.0 / lay_b),
                    ]
                )
                price_spreads.extend([lay_a - back_a, lay_b - back_b])
                if checkpoint.get("market_total_matched") is not None:
                    total_matched.append(float(checkpoint["market_total_matched"]))
                base_rate_total += 1
                if checkpoint.get("market_base_rate") is not None:
                    base_rate_available += 1

    if errors:
        blocked = _blocked_report(errors, manifest)
        return replace(
            blocked,
            source_market_records=len(records),
            source_join_status_counts=dict(sorted(join_status_counts.items())),
            checkpoint_counts={name: checkpoint_counts[name] for name in _CHECKPOINTS},
            executable_checkpoint_counts={name: executable_counts[name] for name in _CHECKPOINTS},
        )

    close_ids = set(close_rows)
    tours = tuple(
        _tour_qa(
            canonical,
            tour=cast(Tour, tour),
            matched_ids=matched_ids,
            close_ids=close_ids,
            start=start,
            end=end,
        )
        for tour in ("ATP", "WTA")
    )
    eligible_count = sum(item.status == "ELIGIBLE_CONFIRMATORY" for item in tours)
    if eligible_count == 2:
        overall_status: OverallStatus = "ELIGIBLE_CONFIRMATORY"
    elif eligible_count == 1:
        overall_status = "PARTIAL_TOUR_ELIGIBILITY"
    else:
        overall_status = "EXPLORATORY_ONLY_COVERAGE"

    return MarketHistQAReport(
        experiment_id=_EXPERIMENT_ID,
        overall_status=overall_status,
        structural_pass=True,
        structural_errors=(),
        bundle_sha256=manifest.bundle_sha256,
        data_package=manifest.data_package,
        requested_start_date=manifest.requested_start_date,
        requested_end_date=manifest.requested_end_date,
        denominator_start_date=start.isoformat(),
        denominator_end_date=interior_end.isoformat(),
        source_market_records=len(records),
        source_join_status_counts=dict(sorted(join_status_counts.items())),
        checkpoint_counts={name: checkpoint_counts[name] for name in _CHECKPOINTS},
        executable_checkpoint_counts={name: executable_counts[name] for name in _CHECKPOINTS},
        close_quote_seconds_to_start=_numeric_summary(quote_ages),
        implied_probability_spread=_numeric_summary(probability_spreads),
        decimal_price_spread=_numeric_summary(price_spreads),
        market_total_matched=_numeric_summary(total_matched),
        market_base_rate_available_fraction=(
            base_rate_available / base_rate_total if base_rate_total else None
        ),
        tours=tours,
    )


def write_market_hist_qa(report: MarketHistQAReport, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run preregistered MARKET-HIST-QA-001 on a Betfair research artifact"
    )
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--market-hist-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_market_hist_qa(
        source_manifest_path=args.source_manifest,
        market_hist_records_path=args.market_hist_records,
        pre_match_path=args.pre_match,
        outcomes_path=args.outcomes,
        source_root=args.source_root,
    )
    write_market_hist_qa(report, args.output)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    if report.overall_status == "BLOCKED_STRUCTURAL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
