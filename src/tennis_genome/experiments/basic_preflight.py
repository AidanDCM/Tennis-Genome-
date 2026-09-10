from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from tennis_genome.data.canonical import PreMatchState, Tour
from tennis_genome.market.historical_batch import (
    build_market_hist_records,
    discover_betfair_files,
    load_pre_match_states,
)

_EXPERIMENT_ID = "BASIC-PREFLIGHT-001"
_PROVIDER_FLOOR = date(2015, 4, 1)
_DEVELOPMENT_END = date(2025, 12, 31)
_RECENT_YEARS = tuple(range(2021, 2026))
_MIN_PRIOR_ROWS = 1000
_RIGHT_EDGE_BUFFER_DAYS = 21


@dataclass(frozen=True)
class SourceFileDigest:
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class YearCoverage:
    year: int
    canonical_proxy_rows: int
    basic_matched_rows: int
    identity_coverage: float


@dataclass(frozen=True)
class MonthCount:
    month: str
    basic_matched_rows: int


@dataclass(frozen=True)
class TourPreflight:
    tour: Tour
    canonical_proxy_rows: int
    basic_matched_rows: int
    identity_coverage: float
    yearly: tuple[YearCoverage, ...]
    monthly_matched: tuple[MonthCount, ...]
    cumulative_prior_before_year: dict[str, int]
    overall_coverage_pass: bool
    recent_coverage_pass: bool
    recent_count_pass: bool
    latest_start_month_with_1000_prior: str | None
    prior_history_pass: bool


@dataclass(frozen=True)
class BasicPreflightReport:
    experiment_id: str
    data_package: str
    requested_start_date: str
    requested_end_date: str
    boundary_safe_end_date: str
    source_file_count: int
    source_total_bytes: int
    source_files: tuple[SourceFileDigest, ...]
    source_bundle_sha256: str
    pre_match_sha256: str
    markets_reconstructed: int
    markets_matched: int
    markets_unmatched: int
    markets_ambiguous: int
    tours: tuple[TourPreflight, ...]
    recommendation_class: str
    recommended_advanced_start_month: str | None
    recommended_advanced_end_date: str | None
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _month_range(start: date, end: date) -> list[date]:
    current = _month_start(start)
    final = _month_start(end)
    result: list[date] = []
    while current <= final:
        result.append(current)
        current = _next_month(current)
    return result


def _source_digests(root: Path) -> tuple[SourceFileDigest, ...]:
    files = discover_betfair_files(root)
    if not files:
        raise ValueError("BASIC source directory contains no supported files")
    result = tuple(
        SourceFileDigest(
            relative_path=path.relative_to(root).as_posix(),
            size_bytes=path.stat().st_size,
            sha256=_sha256_file(path),
        )
        for path in files
    )
    if any(item.size_bytes <= 0 for item in result):
        raise ValueError("BASIC source bundle contains an empty file")
    return result


def _bundle_sha256(files: tuple[SourceFileDigest, ...]) -> str:
    return hashlib.sha256(
        _canonical_json_bytes([asdict(item) for item in files])
    ).hexdigest()


def _safe_states(
    states: list[PreMatchState],
    *,
    start: date,
    safe_end: date,
    tour: Tour,
) -> list[PreMatchState]:
    return [
        state
        for state in states
        if state.tour == tour and start <= state.event_date <= safe_end
    ]


def _latest_start_month(
    matched_states: list[PreMatchState],
    *,
    interval_start: date,
) -> str | None:
    cutoff = date(2020, 12, 31)
    candidates = [
        month
        for month in _month_range(max(interval_start, _PROVIDER_FLOOR), cutoff)
        if month <= cutoff
    ]
    qualifying: list[date] = []
    for candidate in candidates:
        count = sum(
            candidate <= state.event_date <= cutoff
            for state in matched_states
        )
        if count >= _MIN_PRIOR_ROWS:
            qualifying.append(candidate)
    if not qualifying:
        return None
    return max(qualifying).isoformat()


def _tour_report(
    *,
    tour: Tour,
    states: list[PreMatchState],
    matched_ids: set[str],
    start: date,
    safe_end: date,
) -> TourPreflight:
    safe = _safe_states(states, start=start, safe_end=safe_end, tour=tour)
    safe_by_id = {state.match_id: state for state in safe}
    matched_states = [safe_by_id[match_id] for match_id in sorted(matched_ids & safe_by_id.keys())]

    years = list(range(start.year, safe_end.year + 1))
    yearly: list[YearCoverage] = []
    for year in years:
        denominator = sum(state.event_date.year == year for state in safe)
        matched = sum(state.event_date.year == year for state in matched_states)
        yearly.append(
            YearCoverage(
                year=year,
                canonical_proxy_rows=denominator,
                basic_matched_rows=matched,
                identity_coverage=(matched / denominator if denominator else 0.0),
            )
        )

    monthly = tuple(
        MonthCount(
            month=month.isoformat(),
            basic_matched_rows=sum(
                state.event_date.year == month.year and state.event_date.month == month.month
                for state in matched_states
            ),
        )
        for month in _month_range(start, safe_end)
    )
    cumulative = {
        str(year): sum(state.event_date.year < year for state in matched_states)
        for year in years
    }

    denominator_total = len(safe)
    matched_total = len(matched_states)
    overall_coverage = matched_total / denominator_total if denominator_total else 0.0
    by_year = {item.year: item for item in yearly}
    recent_coverage_pass = all(
        by_year.get(year) is not None and by_year[year].identity_coverage >= 0.50
        for year in _RECENT_YEARS
    )
    recent_count_pass = all(
        by_year.get(year) is not None and by_year[year].basic_matched_rows >= 100
        for year in _RECENT_YEARS
    )
    start_month = _latest_start_month(
        matched_states,
        interval_start=start,
    )
    return TourPreflight(
        tour=tour,
        canonical_proxy_rows=denominator_total,
        basic_matched_rows=matched_total,
        identity_coverage=overall_coverage,
        yearly=tuple(yearly),
        monthly_matched=monthly,
        cumulative_prior_before_year=cumulative,
        overall_coverage_pass=overall_coverage >= 0.60,
        recent_coverage_pass=recent_coverage_pass,
        recent_count_pass=recent_count_pass,
        latest_start_month_with_1000_prior=start_month,
        prior_history_pass=start_month is not None,
    )


def build_basic_preflight_report(
    *,
    betfair_root: str | Path,
    pre_match_path: str | Path,
    requested_start_date: str,
    requested_end_date: str,
) -> BasicPreflightReport:
    start = _parse_date(requested_start_date, field="requested_start_date")
    end = _parse_date(requested_end_date, field="requested_end_date")
    if start < _PROVIDER_FLOOR:
        raise ValueError("BASIC preflight source interval cannot begin before 2015-04-01")
    if end > _DEVELOPMENT_END:
        raise ValueError("BASIC preflight source interval must end by 2025-12-31")
    if start > end:
        raise ValueError("requested_start_date must not be after requested_end_date")
    safe_end = end - timedelta(days=_RIGHT_EDGE_BUFFER_DAYS)
    if safe_end < start:
        raise ValueError("source interval is shorter than the 21-day right-edge buffer")

    root = Path(betfair_root)
    pre_match = Path(pre_match_path)
    source_files = _source_digests(root)
    states = load_pre_match_states(pre_match)
    records, _, _ = build_market_hist_records(
        betfair_root=root,
        pre_match_states=states,
        data_package="BASIC",
    )

    matched_records = [record for record in records if record.join is not None]
    matched_ids = [record.join.match_id for record in matched_records if record.join is not None]
    duplicate_matches = [
        match_id
        for match_id, count in Counter(matched_ids).items()
        if count > 1
    ]
    if duplicate_matches:
        raise ValueError(
            "multiple BASIC source markets joined to canonical match IDs: "
            + ", ".join(sorted(duplicate_matches)[:10])
        )
    matched_set = set(matched_ids)

    tours = tuple(
        _tour_report(
            tour=tour,
            states=states,
            matched_ids=matched_set,
            start=start,
            safe_end=safe_end,
        )
        for tour in ("ATP", "WTA")
    )
    starts = [item.latest_start_month_with_1000_prior for item in tours]
    if any(value is None for value in starts):
        recommendation_class = "INSUFFICIENT_BASIC_PRIOR_HISTORY"
        recommended_start = None
        recommended_end = None
    else:
        recommended_start = min(value for value in starts if value is not None)
        recommended_end = _DEVELOPMENT_END.isoformat()
        proxy_pass = all(
            item.overall_coverage_pass
            and item.recent_coverage_pass
            and item.recent_count_pass
            for item in tours
        )
        recommendation_class = (
            "CANDIDATE_MINIMUM_WINDOW" if proxy_pass else "HIGH_RISK_COVERAGE"
        )

    base_payload: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "data_package": "BASIC",
        "requested_start_date": start.isoformat(),
        "requested_end_date": end.isoformat(),
        "boundary_safe_end_date": safe_end.isoformat(),
        "source_file_count": len(source_files),
        "source_total_bytes": sum(item.size_bytes for item in source_files),
        "source_files": [asdict(item) for item in source_files],
        "source_bundle_sha256": _bundle_sha256(source_files),
        "pre_match_sha256": _sha256_file(pre_match),
        "markets_reconstructed": len(records),
        "markets_matched": sum(record.join_status == "MATCHED" for record in records),
        "markets_unmatched": sum(record.join_status == "UNMATCHED" for record in records),
        "markets_ambiguous": sum(record.join_status == "AMBIGUOUS" for record in records),
        "tours": [asdict(item) for item in tours],
        "recommendation_class": recommendation_class,
        "recommended_advanced_start_month": recommended_start,
        "recommended_advanced_end_date": recommended_end,
    }
    artifact_sha = hashlib.sha256(_canonical_json_bytes(base_payload)).hexdigest()
    return BasicPreflightReport(
        experiment_id=_EXPERIMENT_ID,
        data_package="BASIC",
        requested_start_date=start.isoformat(),
        requested_end_date=end.isoformat(),
        boundary_safe_end_date=safe_end.isoformat(),
        source_file_count=len(source_files),
        source_total_bytes=sum(item.size_bytes for item in source_files),
        source_files=source_files,
        source_bundle_sha256=str(base_payload["source_bundle_sha256"]),
        pre_match_sha256=str(base_payload["pre_match_sha256"]),
        markets_reconstructed=len(records),
        markets_matched=int(base_payload["markets_matched"]),
        markets_unmatched=int(base_payload["markets_unmatched"]),
        markets_ambiguous=int(base_payload["markets_ambiguous"]),
        tours=tours,
        recommendation_class=recommendation_class,
        recommended_advanced_start_month=recommended_start,
        recommended_advanced_end_date=recommended_end,
        artifact_sha256=artifact_sha,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run outcome-blind Betfair BASIC purchase-window preflight"
    )
    parser.add_argument("--betfair-root", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = build_basic_preflight_report(
        betfair_root=args.betfair_root,
        pre_match_path=args.pre_match,
        requested_start_date=args.start_date,
        requested_end_date=args.end_date,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
