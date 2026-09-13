from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast

import pandas as pd

from tennis_genome.experiments.market_hist_qa import run_market_hist_qa

CheckpointName = Literal["T-24H", "T-6H", "T-1H", "T-15M", "CLOSE_PREPLAY"]
Tour = Literal["ATP", "WTA"]
_CHECKPOINTS: tuple[CheckpointName, ...] = (
    "T-24H",
    "T-6H",
    "T-1H",
    "T-15M",
    "CLOSE_PREPLAY",
)
_EXPERIMENT_ID = "MARKET-HIST-QA-001"


@dataclass(frozen=True)
class CheckpointCoverage:
    checkpoint_name: CheckpointName
    eligible_canonical: int
    observed_matches: int
    executable_matches: int
    observed_coverage: float | None
    executable_coverage: float | None


@dataclass(frozen=True)
class AnnualCheckpointCoverage:
    year: int
    checkpoints: tuple[CheckpointCoverage, ...]


@dataclass(frozen=True)
class TourCheckpointCoverage:
    tour: Tour
    eligible_canonical: int
    overall: tuple[CheckpointCoverage, ...]
    annual: tuple[AnnualCheckpointCoverage, ...]


@dataclass(frozen=True)
class MarketHistQABundle:
    experiment_id: str
    effective_overall_status: str
    qa_report: dict[str, object]
    checkpoint_coverage: tuple[TourCheckpointCoverage, ...]
    companion_structural_errors: tuple[str, ...]
    input_sha256: dict[str, str]
    artifact_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"MARKET-HIST line {line_number} is not an object")
            rows.append(value)
    return rows


def _eligible_canonical(
    *,
    pre_match_path: str | Path,
    outcomes_path: str | Path,
    start: date,
    end: date,
) -> pd.DataFrame:
    pre = pd.read_parquet(Path(pre_match_path), columns=["match_id", "tour", "event_date"])
    outcomes = pd.read_parquet(
        Path(outcomes_path),
        columns=["match_id", "retirement", "walkover"],
    )
    pre = pre.copy()
    outcomes = outcomes.copy()
    pre["match_id"] = pre["match_id"].astype(str)
    outcomes["match_id"] = outcomes["match_id"].astype(str)
    if pre["match_id"].duplicated().any() or outcomes["match_id"].duplicated().any():
        raise ValueError("canonical QA tables contain duplicate match_id values")
    if set(pre["match_id"]) != set(outcomes["match_id"]):
        raise ValueError("canonical QA pre-match/outcome match-id sets differ")
    pre["event_date"] = pd.to_datetime(pre["event_date"]).dt.date
    merged = pre.merge(outcomes, on="match_id", how="inner", validate="one_to_one")
    if merged[["retirement", "walkover"]].isna().any().any():
        raise ValueError("canonical retirement/walkover flags cannot be missing")
    return merged[
        (merged["event_date"] >= start)
        & (merged["event_date"] <= end)
        & (~merged["retirement"].astype(bool))
        & (~merged["walkover"].astype(bool))
    ].copy()


def _checkpoint_match_sets(
    records: list[dict[str, Any]],
) -> tuple[
    dict[tuple[Tour, CheckpointName], set[str]],
    dict[tuple[Tour, CheckpointName], set[str]],
    list[str],
]:
    observed: dict[tuple[Tour, CheckpointName], set[str]] = defaultdict(set)
    executable: dict[tuple[Tour, CheckpointName], set[str]] = defaultdict(set)
    errors: list[str] = []

    for record_index, record in enumerate(records, start=1):
        if record.get("join_status") != "MATCHED":
            continue
        join = record.get("join")
        if not isinstance(join, dict):
            errors.append(f"record {record_index}: MATCHED record lacks join object")
            continue
        match_id = str(join.get("match_id", ""))
        tour_text = str(join.get("tour", ""))
        source_market_id = str(record.get("source_market_id", ""))
        join_hash = str(join.get("join_hash", ""))
        if tour_text not in {"ATP", "WTA"}:
            errors.append(f"record {record_index}: invalid joined tour {tour_text!r}")
            continue
        if not match_id:
            errors.append(f"record {record_index}: matched join has empty match_id")
            continue
        tour = cast(Tour, tour_text)
        seen_names: set[str] = set()
        checkpoints = record.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            errors.append(f"record {record_index}: checkpoints is not a list")
            continue
        for checkpoint_index, checkpoint in enumerate(checkpoints, start=1):
            if not isinstance(checkpoint, dict):
                errors.append(f"record {record_index} checkpoint {checkpoint_index}: not an object")
                continue
            name_text = str(checkpoint.get("checkpoint_name", ""))
            if name_text not in _CHECKPOINTS:
                continue
            if name_text in seen_names:
                errors.append(
                    f"record {record_index}: duplicate checkpoint {name_text} for one market"
                )
                continue
            seen_names.add(name_text)
            if str(checkpoint.get("match_id", "")) != match_id:
                errors.append(
                    f"record {record_index} {name_text}: checkpoint match_id disagrees with join"
                )
                continue
            if str(checkpoint.get("source_market_id", "")) != source_market_id:
                errors.append(
                    f"record {record_index} {name_text}: checkpoint market ID disagrees with record"
                )
                continue
            if str(checkpoint.get("join_hash", "")) != join_hash:
                errors.append(
                    f"record {record_index} {name_text}: checkpoint join hash disagrees with join"
                )
                continue
            key = (tour, cast(CheckpointName, name_text))
            observed[key].add(match_id)
            if checkpoint.get("executable_two_way") is True:
                executable[key].add(match_id)
    return observed, executable, errors


def _coverage_row(
    *,
    checkpoint: CheckpointName,
    eligible_ids: set[str],
    observed_ids: set[str],
    executable_ids: set[str],
) -> CheckpointCoverage:
    denominator = len(eligible_ids)
    observed_n = len(eligible_ids.intersection(observed_ids))
    executable_n = len(eligible_ids.intersection(executable_ids))
    return CheckpointCoverage(
        checkpoint_name=checkpoint,
        eligible_canonical=denominator,
        observed_matches=observed_n,
        executable_matches=executable_n,
        observed_coverage=(observed_n / denominator) if denominator else None,
        executable_coverage=(executable_n / denominator) if denominator else None,
    )


def _checkpoint_coverage(
    *,
    eligible: pd.DataFrame,
    observed: dict[tuple[Tour, CheckpointName], set[str]],
    executable: dict[tuple[Tour, CheckpointName], set[str]],
) -> tuple[TourCheckpointCoverage, ...]:
    tours: list[TourCheckpointCoverage] = []
    for tour in cast(tuple[Tour, Tour], ("ATP", "WTA")):
        tour_frame = eligible[eligible["tour"].astype(str) == tour].copy()
        tour_ids = set(tour_frame["match_id"].astype(str))
        overall = tuple(
            _coverage_row(
                checkpoint=checkpoint,
                eligible_ids=tour_ids,
                observed_ids=observed[(tour, checkpoint)],
                executable_ids=executable[(tour, checkpoint)],
            )
            for checkpoint in _CHECKPOINTS
        )
        annual: list[AnnualCheckpointCoverage] = []
        years = sorted({value.year for value in tour_frame["event_date"]})
        for year in years:
            year_frame = tour_frame[tour_frame["event_date"].map(lambda value: value.year) == year]
            year_ids = set(year_frame["match_id"].astype(str))
            annual.append(
                AnnualCheckpointCoverage(
                    year=year,
                    checkpoints=tuple(
                        _coverage_row(
                            checkpoint=checkpoint,
                            eligible_ids=year_ids,
                            observed_ids=observed[(tour, checkpoint)],
                            executable_ids=executable[(tour, checkpoint)],
                        )
                        for checkpoint in _CHECKPOINTS
                    ),
                )
            )
        tours.append(
            TourCheckpointCoverage(
                tour=tour,
                eligible_canonical=len(tour_ids),
                overall=overall,
                annual=tuple(annual),
            )
        )
    return tuple(tours)


def build_market_hist_qa_bundle(
    *,
    source_manifest_path: str | Path,
    market_hist_records_path: str | Path,
    pre_match_path: str | Path,
    outcomes_path: str | Path,
    source_root: str | Path | None = None,
) -> MarketHistQABundle:
    qa = run_market_hist_qa(
        source_manifest_path=source_manifest_path,
        market_hist_records_path=market_hist_records_path,
        pre_match_path=pre_match_path,
        outcomes_path=outcomes_path,
        source_root=source_root,
    )
    qa_dict = qa.to_dict()
    companion_errors: list[str] = []
    checkpoint_coverage: tuple[TourCheckpointCoverage, ...] = ()

    if qa.structural_pass:
        try:
            denominator_start = date.fromisoformat(cast(str, qa.denominator_start_date))
            denominator_end = date.fromisoformat(cast(str, qa.denominator_end_date))
            eligible = _eligible_canonical(
                pre_match_path=pre_match_path,
                outcomes_path=outcomes_path,
                start=denominator_start,
                end=denominator_end,
            )
            records = _load_jsonl(market_hist_records_path)
            observed, executable, companion_errors = _checkpoint_match_sets(records)
            if not companion_errors:
                checkpoint_coverage = _checkpoint_coverage(
                    eligible=eligible,
                    observed=observed,
                    executable=executable,
                )
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
            companion_errors.append(f"checkpoint coverage validation failed: {exc}")

    effective_status = "BLOCKED_STRUCTURAL" if companion_errors else qa.overall_status
    paths = {
        "source_manifest": Path(source_manifest_path),
        "market_hist_records": Path(market_hist_records_path),
        "pre_match": Path(pre_match_path),
        "outcomes": Path(outcomes_path),
    }
    input_hashes = {name: _sha256_file(path) for name, path in sorted(paths.items())}
    unsigned = {
        "experiment_id": _EXPERIMENT_ID,
        "effective_overall_status": effective_status,
        "qa_report": qa_dict,
        "checkpoint_coverage": [asdict(value) for value in checkpoint_coverage],
        "companion_structural_errors": sorted(set(companion_errors)),
        "input_sha256": input_hashes,
    }
    artifact_hash = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return MarketHistQABundle(
        experiment_id=_EXPERIMENT_ID,
        effective_overall_status=effective_status,
        qa_report=qa_dict,
        checkpoint_coverage=checkpoint_coverage,
        companion_structural_errors=tuple(sorted(set(companion_errors))),
        input_sha256=input_hashes,
        artifact_sha256=artifact_hash,
    )


def write_market_hist_qa_bundle(bundle: MarketHistQABundle, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MARKET-HIST-QA-001 with checkpoint-specific coverage reporting"
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
    bundle = build_market_hist_qa_bundle(
        source_manifest_path=args.source_manifest,
        market_hist_records_path=args.market_hist_records,
        pre_match_path=args.pre_match,
        outcomes_path=args.outcomes,
        source_root=args.source_root,
    )
    write_market_hist_qa_bundle(bundle, args.output)
    print(json.dumps(bundle.to_dict(), indent=2, sort_keys=True))
    if bundle.effective_overall_status == "BLOCKED_STRUCTURAL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
