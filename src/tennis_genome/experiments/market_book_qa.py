from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from tennis_genome.market.bookmaker_manifest import (
    BookmakerSourceManifest,
    load_bookmaker_source_manifest,
    verify_bookmaker_source_manifest,
)

Tour = Literal["ATP", "WTA"]
_EXPERIMENT_ID = "MARKET-BOOK-QA-001"
_MARKET_POLICY = "BOOKMAKER_CLOSE_V1"
_BATCH_VERSION = "market-book-001-batch-v1"
_RESOLVER_VERSION = "bookmaker-canonical-join-v1"
_DEVELOPMENT_END = date(2025, 12, 31)
_END_BUFFER_DAYS = 21
_MIN_OVERALL_COVERAGE = 0.60
_MIN_RECENT_COVERAGE = 0.50
_MIN_RECENT_ROWS = 100
_MIN_PRIOR_ROWS = 1000
_RECENT_YEARS = (2021, 2022, 2023, 2024, 2025)
_PRE_MATCH_FORBIDDEN = {"a_won", "score", "retirement", "walkover"}


@dataclass(frozen=True)
class NumericSummary:
    n: int
    minimum: float | None
    median: float | None
    p90: float | None
    p95: float | None
    maximum: float | None
    mean: float | None


@dataclass(frozen=True)
class AnnualBookmakerCoverage:
    year: int
    eligible_canonical: int
    usable_close: int
    close_coverage: float | None


@dataclass(frozen=True)
class BookmakerCoverageGates:
    overall_close_coverage_at_least_60pct: bool
    every_recent_year_close_coverage_at_least_50pct: bool
    every_recent_year_at_least_100_rows: bool
    at_least_1000_prior_rows_before_first_evaluation_year: bool
    all_2021_2025_years_in_evaluation_population: bool
    passed: bool


@dataclass(frozen=True)
class BookmakerTourQA:
    tour: Tour
    status: str
    eligible_canonical: int
    usable_close: int
    overall_close_coverage: float | None
    prior_rows_before_2021: int
    annual: tuple[AnnualBookmakerCoverage, ...]
    selected_source_counts: dict[str, int]
    gates: BookmakerCoverageGates


@dataclass(frozen=True)
class MarketBookQAReport:
    experiment_id: str
    overall_status: str
    structural_pass: bool
    bundle_sha256: str
    requested_start_date: str
    requested_end_date: str
    denominator_start_date: str
    denominator_end_date: str
    source_record_count: int
    join_status_counts: dict[str, int]
    selected_source_counts: dict[str, int]
    invalid_quote_rows: int
    source_conflict_rows: int
    overlap_matches: int
    overlap_probability_abs_difference: NumericSummary
    tours: tuple[BookmakerTourQA, ...]
    records_sha256: str
    input_sha256: dict[str, str]
    artifact_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _numeric_summary(values: list[float]) -> NumericSummary:
    finite = np.asarray([value for value in values if math.isfinite(value)], dtype=float)
    if finite.size == 0:
        return NumericSummary(0, None, None, None, None, None, None)
    return NumericSummary(
        n=int(finite.size),
        minimum=float(np.min(finite)),
        median=float(np.median(finite)),
        p90=float(np.quantile(finite, 0.90)),
        p95=float(np.quantile(finite, 0.95)),
        maximum=float(np.max(finite)),
        mean=float(np.mean(finite)),
    )


def _load_records(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid MARKET-BOOK JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number}: MARKET-BOOK record must be an object")
            records.append(value)
    if not records:
        raise ValueError("MARKET-BOOK artifact contains no records")
    return records


def _manifest_file_map(manifest: BookmakerSourceManifest) -> dict[str, tuple[str, str]]:
    return {
        f"{item.root_key}/{item.relative_path}": (item.sha256, item.source_family)
        for item in manifest.files
    }


def _valid_sha(value: object) -> bool:
    text = str(value).lower()
    return len(text) == 64 and all(c in "0123456789abcdef" for c in text)


def _expected_join_hash(record: dict[str, Any]) -> str:
    join = record.get("join")
    if not isinstance(join, dict):
        raise ValueError("matched bookmaker record lacks join object")
    payload = {
        "resolver_version": _RESOLVER_VERSION,
        "sanitized_row_hash": str(record["sanitized_row_hash"]),
        "match_id": str(join["match_id"]),
        "player_a_id": str(join["player_a_id"]),
        "player_b_id": str(join["player_b_id"]),
        "offset_days": int(join["tournament_date_offset_days"]),
        "days_before": int(join["days_before_window"]),
        "days_after": int(join["days_after_window"]),
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _record_structural_checks(
    records: list[dict[str, Any]],
    *,
    manifest: BookmakerSourceManifest,
) -> None:
    manifest_files = _manifest_file_map(manifest)
    selected_by_match: dict[str, int] = Counter()
    valid_valuebet_matches: set[str] = set()

    for index, record in enumerate(records, start=1):
        if record.get("batch_version") != _BATCH_VERSION:
            raise ValueError(f"record {index}: unexpected MARKET-BOOK batch version")
        if record.get("market_policy") != _MARKET_POLICY:
            raise ValueError(f"record {index}: unexpected market policy")
        source_file = str(record.get("source_file", ""))
        if source_file not in manifest_files:
            raise ValueError(f"record {index}: source file not present in manifest")
        expected_hash, expected_family = manifest_files[source_file]
        if str(record.get("source_file_sha256", "")).lower() != expected_hash:
            raise ValueError(f"record {index}: source hash disagrees with manifest")
        if str(record.get("source_family", "")) != expected_family:
            raise ValueError(f"record {index}: source family disagrees with manifest")
        if not _valid_sha(record.get("sanitized_row_hash")):
            raise ValueError(f"record {index}: invalid sanitized row hash")

        provided_record_hash = str(record.get("record_hash", "")).lower()
        payload = {key: value for key, value in record.items() if key != "record_hash"}
        expected_record_hash = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
        if provided_record_hash != expected_record_hash:
            raise ValueError(f"record {index}: record hash mismatch")

        try:
            match_date = date.fromisoformat(str(record.get("match_date", "")))
        except ValueError as exc:
            raise ValueError(f"record {index}: invalid match_date") from exc
        if match_date > _DEVELOPMENT_END:
            raise ValueError(f"record {index}: post-2025 quote in confirmatory artifact")

        status = str(record.get("join_status", ""))
        if status not in {"MATCHED", "UNMATCHED", "AMBIGUOUS"}:
            raise ValueError(f"record {index}: invalid join_status")
        join = record.get("join")
        if status == "MATCHED":
            if not isinstance(join, dict):
                raise ValueError(f"record {index}: MATCHED record lacks join")
            if str(join.get("resolver_version")) != _RESOLVER_VERSION:
                raise ValueError(f"record {index}: unexpected join resolver version")
            if str(join.get("join_hash", "")).lower() != _expected_join_hash(record):
                raise ValueError(f"record {index}: join hash mismatch")
            if str(join.get("tour")) != str(record.get("tour")):
                raise ValueError(f"record {index}: join tour disagrees with source tour")
        elif join is not None:
            raise ValueError(f"record {index}: non-matched record contains join")

        if record.get("quote_valid") is True and status == "MATCHED":
            odds_a = float(record["decimal_odds_a"])
            odds_b = float(record["decimal_odds_b"])
            p_a = float(record["market_probability_a"])
            p_b = float(record["market_probability_b"])
            if not all(math.isfinite(value) for value in (odds_a, odds_b, p_a, p_b)):
                raise ValueError(f"record {index}: non-finite selected market values")
            if odds_a <= 1.0 or odds_b <= 1.0:
                raise ValueError(f"record {index}: invalid decimal odds")
            if not 0.0 < p_a < 1.0 or not 0.0 < p_b < 1.0:
                raise ValueError(f"record {index}: invalid no-vig probability")
            if not math.isclose(p_a + p_b, 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"record {index}: no-vig probabilities do not sum to one")
            if (
                record.get("source_family") == "VALUEBETENNIS"
                and record.get("source_conflict") is not True
                and record.get("duplicate_of_sanitized_row_hash") is None
            ):
                valid_valuebet_matches.add(str(join["match_id"]))

        if record.get("selected_primary") is True:
            if status != "MATCHED" or record.get("quote_valid") is not True:
                raise ValueError(f"record {index}: selected quote is not a valid matched quote")
            if record.get("source_conflict") is True:
                raise ValueError(f"record {index}: conflicting source quote was selected")
            if record.get("duplicate_of_sanitized_row_hash") is not None:
                raise ValueError(f"record {index}: duplicate source row was selected")
            if record.get("selected_policy") != _MARKET_POLICY:
                raise ValueError(f"record {index}: selected policy mismatch")
            if not isinstance(join, dict):
                raise ValueError(f"record {index}: selected quote lacks join")
            selected_by_match[str(join["match_id"])] += 1
        elif record.get("selected_policy") is not None:
            raise ValueError(f"record {index}: unselected quote has selected_policy")

    duplicates = sorted(match_id for match_id, count in selected_by_match.items() if count != 1)
    if duplicates:
        raise ValueError(
            f"multiple selected primary quotes for canonical matches: {duplicates[:5]}"
        )
    for record in records:
        if record.get("selected_primary") is not True:
            continue
        join = cast(dict[str, Any], record["join"])
        match_id = str(join["match_id"])
        if record.get("source_family") == "TENNIS_DATA_UK" and match_id in valid_valuebet_matches:
            raise ValueError("selected Tennis-Data quote violates frozen Valuebetennis priority")


def _load_eligible_canonical(
    *,
    pre_match_path: str | Path,
    outcomes_path: str | Path,
    denominator_start: date,
    denominator_end: date,
) -> pd.DataFrame:
    pre = pd.read_parquet(Path(pre_match_path))
    leaked = sorted(_PRE_MATCH_FORBIDDEN.intersection(pre.columns))
    if leaked:
        raise ValueError(f"outcome fields leaked into pre-match table: {leaked}")
    required_pre = {"match_id", "tour", "event_date"}
    missing_pre = sorted(required_pre.difference(pre.columns))
    if missing_pre:
        raise ValueError(f"pre-match table missing required columns: {missing_pre}")
    if pre["match_id"].astype(str).duplicated().any():
        raise ValueError("pre-match table contains duplicate match_id values")

    outcomes = pd.read_parquet(Path(outcomes_path))
    required_outcome = {"match_id", "retirement", "walkover"}
    missing_outcome = sorted(required_outcome.difference(outcomes.columns))
    if missing_outcome:
        raise ValueError(f"outcome table missing required columns: {missing_outcome}")
    if outcomes["match_id"].astype(str).duplicated().any():
        raise ValueError("outcome table contains duplicate match_id values")
    outcome = outcomes[["match_id", "retirement", "walkover"]].copy()
    if outcome[["retirement", "walkover"]].isna().any().any():
        raise ValueError("outcome eligibility fields cannot be missing")

    frame = pre[["match_id", "tour", "event_date"]].copy()
    frame["match_id"] = frame["match_id"].astype(str)
    outcome["match_id"] = outcome["match_id"].astype(str)
    frame["event_date"] = pd.to_datetime(frame["event_date"]).dt.date
    frame = frame[
        (frame["event_date"] >= denominator_start)
        & (frame["event_date"] <= denominator_end)
    ].copy()
    frame = frame.merge(
        outcome,
        on="match_id",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    missing_outcomes = frame.loc[frame["_merge"] != "both", "match_id"].astype(str).tolist()
    if missing_outcomes:
        raise ValueError(
            "outcome ledger is incomplete for canonical QA denominator: "
            f"{missing_outcomes[:5]}"
        )
    frame = frame.drop(columns=["_merge"])
    frame = frame[
        (~frame["retirement"].astype(bool))
        & (~frame["walkover"].astype(bool))
    ].copy()
    if not set(frame["tour"].astype(str)).issubset({"ATP", "WTA"}):
        raise ValueError("canonical QA population contains invalid tour")
    frame["year"] = pd.to_datetime(frame["event_date"]).dt.year
    return frame


def _selected_rows(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("selected_primary") is not True:
            continue
        join = cast(dict[str, Any], record["join"])
        match_id = str(join["match_id"])
        if match_id in result:
            raise ValueError("duplicate selected primary match after structural validation")
        result[match_id] = record
    return result


def _overlap_differences(records: list[dict[str, Any]]) -> list[float]:
    by_match_source: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in records:
        if (
            record.get("join_status") != "MATCHED"
            or record.get("quote_valid") is not True
            or record.get("source_conflict") is True
            or record.get("duplicate_of_sanitized_row_hash") is not None
        ):
            continue
        join = record.get("join")
        if not isinstance(join, dict):
            continue
        probability = float(record["market_probability_a"])
        by_match_source[(str(join["match_id"]), str(record["source_family"]))].append(probability)
    matches = {match_id for match_id, _ in by_match_source}
    differences: list[float] = []
    for match_id in matches:
        left = by_match_source.get((match_id, "VALUEBETENNIS"), [])
        right = by_match_source.get((match_id, "TENNIS_DATA_UK"), [])
        if len(left) == 1 and len(right) == 1:
            differences.append(abs(left[0] - right[0]))
    return differences


def _tour_qa(
    *,
    tour: Tour,
    eligible: pd.DataFrame,
    selected: dict[str, dict[str, Any]],
) -> BookmakerTourQA:
    tour_frame = eligible[eligible["tour"].astype(str) == tour].copy()
    selected_ids = set(selected)
    covered_mask = tour_frame["match_id"].isin(selected_ids)
    eligible_n = len(tour_frame)
    usable_n = int(covered_mask.sum())
    overall = None if eligible_n == 0 else usable_n / eligible_n

    annual: list[AnnualBookmakerCoverage] = []
    for year in _RECENT_YEARS:
        year_frame = tour_frame[tour_frame["year"] == year]
        year_eligible = len(year_frame)
        year_usable = int(year_frame["match_id"].isin(selected_ids).sum())
        annual.append(
            AnnualBookmakerCoverage(
                year=year,
                eligible_canonical=year_eligible,
                usable_close=year_usable,
                close_coverage=None if year_eligible == 0 else year_usable / year_eligible,
            )
        )

    prior_frame = tour_frame[tour_frame["year"] < 2021]
    prior_rows = int(prior_frame["match_id"].isin(selected_ids).sum())
    recent_coverage_pass = all(
        row.close_coverage is not None and row.close_coverage >= _MIN_RECENT_COVERAGE
        for row in annual
    )
    recent_rows_pass = all(row.usable_close >= _MIN_RECENT_ROWS for row in annual)
    represented = all(row.eligible_canonical > 0 and row.usable_close > 0 for row in annual)
    gates = BookmakerCoverageGates(
        overall_close_coverage_at_least_60pct=(
            overall is not None and overall >= _MIN_OVERALL_COVERAGE
        ),
        every_recent_year_close_coverage_at_least_50pct=recent_coverage_pass,
        every_recent_year_at_least_100_rows=recent_rows_pass,
        at_least_1000_prior_rows_before_first_evaluation_year=prior_rows >= _MIN_PRIOR_ROWS,
        all_2021_2025_years_in_evaluation_population=represented,
        passed=False,
    )
    passed = all(
        (
            gates.overall_close_coverage_at_least_60pct,
            gates.every_recent_year_close_coverage_at_least_50pct,
            gates.every_recent_year_at_least_100_rows,
            gates.at_least_1000_prior_rows_before_first_evaluation_year,
            gates.all_2021_2025_years_in_evaluation_population,
        )
    )
    gates = BookmakerCoverageGates(**{**asdict(gates), "passed": passed})
    selected_sources = Counter(
        str(selected[match_id]["source_family"])
        for match_id in tour_frame.loc[covered_mask, "match_id"].astype(str)
    )
    return BookmakerTourQA(
        tour=tour,
        status="ELIGIBLE_CONFIRMATORY" if passed else "INSUFFICIENT_COVERAGE",
        eligible_canonical=eligible_n,
        usable_close=usable_n,
        overall_close_coverage=overall,
        prior_rows_before_2021=prior_rows,
        annual=tuple(annual),
        selected_source_counts=dict(sorted(selected_sources.items())),
        gates=gates,
    )


def run_market_book_qa(
    *,
    source_manifest_path: str | Path,
    market_book_records_path: str | Path,
    pre_match_path: str | Path,
    outcomes_path: str | Path,
    valuebet_root: str | Path,
    tennis_data_atp_root: str | Path,
    tennis_data_wta_root: str | Path,
) -> MarketBookQAReport:
    manifest = load_bookmaker_source_manifest(source_manifest_path)
    verify_bookmaker_source_manifest(
        manifest,
        valuebet_root=valuebet_root,
        tennis_data_atp_root=tennis_data_atp_root,
        tennis_data_wta_root=tennis_data_wta_root,
    )
    records = _load_records(market_book_records_path)
    _record_structural_checks(records, manifest=manifest)

    start = date.fromisoformat(manifest.requested_start_date)
    end = date.fromisoformat(manifest.requested_end_date)
    denominator_end = end - timedelta(days=_END_BUFFER_DAYS)
    if denominator_end < start:
        raise ValueError("bookmaker source interval is too short for denominator buffer")
    eligible = _load_eligible_canonical(
        pre_match_path=pre_match_path,
        outcomes_path=outcomes_path,
        denominator_start=start,
        denominator_end=denominator_end,
    )
    selected = _selected_rows(records)
    tours = (
        _tour_qa(tour="ATP", eligible=eligible, selected=selected),
        _tour_qa(tour="WTA", eligible=eligible, selected=selected),
    )
    overall = (
        "ELIGIBLE_CONFIRMATORY"
        if all(tour.status == "ELIGIBLE_CONFIRMATORY" for tour in tours)
        else "INSUFFICIENT_COVERAGE"
    )
    overlap = _overlap_differences(records)
    join_counts = Counter(str(record.get("join_status")) for record in records)
    selected_sources = Counter(
        str(record["source_family"])
        for record in records
        if record.get("selected_primary") is True
    )
    input_hashes = {
        "source_manifest": _sha256_file(source_manifest_path),
        "market_book_records": _sha256_file(market_book_records_path),
        "pre_match": _sha256_file(pre_match_path),
        "outcomes": _sha256_file(outcomes_path),
    }
    report = MarketBookQAReport(
        experiment_id=_EXPERIMENT_ID,
        overall_status=overall,
        structural_pass=True,
        bundle_sha256=manifest.bundle_sha256,
        requested_start_date=start.isoformat(),
        requested_end_date=end.isoformat(),
        denominator_start_date=start.isoformat(),
        denominator_end_date=denominator_end.isoformat(),
        source_record_count=len(records),
        join_status_counts=dict(sorted(join_counts.items())),
        selected_source_counts=dict(sorted(selected_sources.items())),
        invalid_quote_rows=sum(record.get("quote_valid") is not True for record in records),
        source_conflict_rows=sum(record.get("source_conflict") is True for record in records),
        overlap_matches=len(overlap),
        overlap_probability_abs_difference=_numeric_summary(overlap),
        tours=tours,
        records_sha256=input_hashes["market_book_records"],
        input_sha256=input_hashes,
        artifact_sha256="",
    )
    unsigned = report.to_dict()
    unsigned.pop("artifact_sha256", None)
    artifact_hash = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return replace(report, artifact_sha256=artifact_hash)


def write_market_book_qa(report: MarketBookQAReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run outcome-blind MARKET-BOOK-QA-001 coverage gate"
    )
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--market-book-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--valuebet-root", required=True, type=Path)
    parser.add_argument("--tennis-data-atp-root", required=True, type=Path)
    parser.add_argument("--tennis-data-wta-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_market_book_qa(
        source_manifest_path=args.source_manifest,
        market_book_records_path=args.market_book_records,
        pre_match_path=args.pre_match,
        outcomes_path=args.outcomes,
        valuebet_root=args.valuebet_root,
        tennis_data_atp_root=args.tennis_data_atp_root,
        tennis_data_wta_root=args.tennis_data_wta_root,
    )
    write_market_book_qa(report, args.output)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
