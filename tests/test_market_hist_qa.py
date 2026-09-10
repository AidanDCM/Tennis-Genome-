from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.experiments.market_hist_qa import run_market_hist_qa
from tennis_genome.experiments.market_hist_qa_bundle import (
    build_market_hist_qa_bundle,
    write_market_hist_qa_bundle,
)
from tennis_genome.market.historical_manifest import (
    build_historical_source_manifest,
    write_historical_source_manifest,
)


@dataclass(frozen=True)
class QACase:
    root: Path
    manifest: Path
    records: Path
    pre_match: Path
    outcomes: Path


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _checkpoint(
    *,
    name: str,
    match_id: str,
    market_id: str,
    join_hash: str,
    source_hash: str,
    market_time: datetime,
    seconds_to_start: float,
    executable: bool = True,
) -> dict[str, object]:
    published = market_time - timedelta(seconds=seconds_to_start)
    return {
        "checkpoint_name": name,
        "data_package": "ADVANCED",
        "executable_two_way": executable,
        "seconds_to_start": seconds_to_start,
        "checkpoint_lag_seconds": 0.0,
        "match_id": match_id,
        "source_market_id": market_id,
        "best_back_a": 1.90,
        "best_back_size_a": 100.0,
        "best_lay_a": 1.92,
        "best_lay_size_a": 90.0,
        "best_back_b": 2.05,
        "best_back_size_b": 80.0,
        "best_lay_b": 2.08,
        "best_lay_size_b": 70.0,
        "published_at": published.isoformat(),
        "market_time": market_time.isoformat(),
        "market_total_matched": 5000.0,
        "market_base_rate": 5.0,
        "record_hash": _sha(f"record:{match_id}:{name}"),
        "join_hash": join_hash,
        "source_file_sha256": source_hash,
        "source_message_sha256": _sha(f"message:{match_id}:{name}"),
    }


def _build_case(
    root: Path,
    *,
    wta_2024_close_fraction: float = 1.0,
    tamper_record_source_hash: bool = False,
) -> QACase:
    source_root = root / "source"
    source_root.mkdir(parents=True)
    source_file = source_root / "bundle.dat"
    source_file.write_bytes(b"synthetic licensed-source stand-in")
    manifest = build_historical_source_manifest(
        root=source_root,
        data_package="ADVANCED",
        requested_start_date="2020-01-01",
        requested_end_date="2025-12-31",
    )
    manifest_path = root / "manifest.json"
    write_historical_source_manifest(manifest, manifest_path)
    source_hash = manifest.files[0].sha256

    pre_rows: list[dict[str, object]] = []
    outcome_rows: list[dict[str, object]] = []
    market_lines: list[str] = []

    for tour in ("ATP", "WTA"):
        for year in range(2020, 2026):
            count = 1000 if year == 2020 else 100
            for index in range(count):
                match_id = f"{tour.lower()}-{year}-{index:04d}"
                event_date = date(year, 6, 15)
                pre_rows.append(
                    {
                        "match_id": match_id,
                        "tour": tour,
                        "event_date": event_date,
                        "tournament_level": "A" if index % 2 == 0 else "M",
                        "surface": "Hard" if index % 3 else "Clay",
                        "round": "R32" if index % 2 == 0 else "R16",
                        "rank_a": 10 + (index % 120),
                        "rank_b": 20 + (index % 140),
                    }
                )
                outcome_rows.append(
                    {
                        "match_id": match_id,
                        "retirement": False,
                        "walkover": False,
                    }
                )
                market_id = f"market-{match_id}"
                join_hash = _sha(f"join:{match_id}")
                market_time = datetime(year, 6, 15, 18, 0, tzinfo=UTC)
                close_executable = not (
                    tour == "WTA"
                    and year == 2024
                    and index >= int(count * wta_2024_close_fraction)
                )
                checkpoints = [
                    _checkpoint(
                        name="CLOSE_PREPLAY",
                        match_id=match_id,
                        market_id=market_id,
                        join_hash=join_hash,
                        source_hash=source_hash,
                        market_time=market_time,
                        seconds_to_start=300.0,
                        executable=close_executable,
                    ),
                    _checkpoint(
                        name="T-15M",
                        match_id=match_id,
                        market_id=market_id,
                        join_hash=join_hash,
                        source_hash=source_hash,
                        market_time=market_time,
                        seconds_to_start=900.0,
                    ),
                ]
                if index % 2 == 0:
                    checkpoints.append(
                        _checkpoint(
                            name="T-1H",
                            match_id=match_id,
                            market_id=market_id,
                            join_hash=join_hash,
                            source_hash=source_hash,
                            market_time=market_time,
                            seconds_to_start=3600.0,
                        )
                    )
                if index % 4 == 0:
                    checkpoints.append(
                        _checkpoint(
                            name="T-6H",
                            match_id=match_id,
                            market_id=market_id,
                            join_hash=join_hash,
                            source_hash=source_hash,
                            market_time=market_time,
                            seconds_to_start=21600.0,
                        )
                    )
                if index % 10 == 0:
                    checkpoints.append(
                        _checkpoint(
                            name="T-24H",
                            match_id=match_id,
                            market_id=market_id,
                            join_hash=join_hash,
                            source_hash=source_hash,
                            market_time=market_time,
                            seconds_to_start=86400.0,
                        )
                    )
                record_source_hash = (
                    "f" * 64
                    if tamper_record_source_hash and not market_lines
                    else source_hash
                )
                market_lines.append(
                    json.dumps(
                        {
                            "source_market_id": market_id,
                            "source_event_id": f"event-{year}",
                            "source_file": "bundle.dat",
                            "source_file_sha256": record_source_hash,
                            "data_package": "ADVANCED",
                            "join_status": "MATCHED",
                            "normalized_runner_names": ["alpha", "beta"],
                            "candidate_match_ids": [match_id],
                            "join": {
                                "join_hash": join_hash,
                                "source_market_id": market_id,
                                "match_id": match_id,
                                "tour": tour,
                            },
                            "checkpoints": checkpoints,
                        },
                        sort_keys=True,
                    )
                )

        boundary_id = f"{tour.lower()}-boundary-excluded"
        pre_rows.append(
            {
                "match_id": boundary_id,
                "tour": tour,
                "event_date": date(2025, 12, 20),
                "tournament_level": "A",
                "surface": "Hard",
                "round": "R32",
                "rank_a": 20,
                "rank_b": 30,
            }
        )
        outcome_rows.append(
            {"match_id": boundary_id, "retirement": False, "walkover": False}
        )

    records_path = root / "market_hist_001_records.jsonl"
    records_path.write_text("\n".join(market_lines) + "\n", encoding="utf-8")
    pre_path = root / "pre_match.parquet"
    outcomes_path = root / "outcomes.parquet"
    pd.DataFrame(pre_rows).to_parquet(pre_path, index=False)
    pd.DataFrame(outcome_rows).to_parquet(outcomes_path, index=False)
    return QACase(
        root=source_root,
        manifest=manifest_path,
        records=records_path,
        pre_match=pre_path,
        outcomes=outcomes_path,
    )


@pytest.fixture(scope="module")
def eligible_case(tmp_path_factory: pytest.TempPathFactory) -> QACase:
    return _build_case(tmp_path_factory.mktemp("market_hist_qa_eligible"))


def test_full_case_is_confirmatory_eligible_and_uses_21_day_boundary(
    eligible_case: QACase,
) -> None:
    report = run_market_hist_qa(
        source_manifest_path=eligible_case.manifest,
        market_hist_records_path=eligible_case.records,
        pre_match_path=eligible_case.pre_match,
        outcomes_path=eligible_case.outcomes,
        source_root=eligible_case.root,
    )
    assert report.structural_pass is True
    assert report.overall_status == "ELIGIBLE_CONFIRMATORY"
    assert report.denominator_end_date == "2025-12-10"
    assert len(report.tours) == 2
    for tour in report.tours:
        assert tour.status == "ELIGIBLE_CONFIRMATORY"
        assert tour.eligible_canonical == 1500
        assert tour.executable_close == 1500
        assert tour.first_confirmatory_evaluation_year == 2021
        assert tour.prior_rows_before_first_evaluation_year == 1000
        assert tour.confirmatory_evaluation_years == (2021, 2022, 2023, 2024, 2025)
        assert tour.gates.passed is True
        assert tour.group_coverage


def test_checkpoint_companion_reports_per_tour_and_year_coverage(
    eligible_case: QACase,
) -> None:
    bundle = build_market_hist_qa_bundle(
        source_manifest_path=eligible_case.manifest,
        market_hist_records_path=eligible_case.records,
        pre_match_path=eligible_case.pre_match,
        outcomes_path=eligible_case.outcomes,
        source_root=eligible_case.root,
    )
    assert bundle.effective_overall_status == "ELIGIBLE_CONFIRMATORY"
    assert bundle.companion_structural_errors == ()
    assert len(bundle.artifact_sha256) == 64
    atp = next(item for item in bundle.checkpoint_coverage if item.tour == "ATP")
    overall = {item.checkpoint_name: item for item in atp.overall}
    assert overall["CLOSE_PREPLAY"].executable_coverage == pytest.approx(1.0)
    assert overall["T-15M"].executable_coverage == pytest.approx(1.0)
    assert overall["T-1H"].executable_coverage == pytest.approx(0.5)
    assert overall["T-6H"].executable_coverage == pytest.approx(0.25)
    assert overall["T-24H"].executable_coverage == pytest.approx(0.10)
    year_2024 = next(item for item in atp.annual if item.year == 2024)
    annual = {item.checkpoint_name: item for item in year_2024.checkpoints}
    assert annual["CLOSE_PREPLAY"].eligible_canonical == 100
    assert annual["T-1H"].executable_matches == 50


def test_checkpoint_bundle_serialization_is_deterministic(
    eligible_case: QACase,
    tmp_path: Path,
) -> None:
    first = build_market_hist_qa_bundle(
        source_manifest_path=eligible_case.manifest,
        market_hist_records_path=eligible_case.records,
        pre_match_path=eligible_case.pre_match,
        outcomes_path=eligible_case.outcomes,
        source_root=eligible_case.root,
    )
    second = build_market_hist_qa_bundle(
        source_manifest_path=eligible_case.manifest,
        market_hist_records_path=eligible_case.records,
        pre_match_path=eligible_case.pre_match,
        outcomes_path=eligible_case.outcomes,
        source_root=eligible_case.root,
    )
    assert first == second
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    write_market_hist_qa_bundle(first, path_a)
    write_market_hist_qa_bundle(second, path_b)
    assert path_a.read_bytes() == path_b.read_bytes()


def test_one_tour_can_be_exploratory_without_redefining_other_tour(tmp_path: Path) -> None:
    case = _build_case(tmp_path, wta_2024_close_fraction=0.40)
    report = run_market_hist_qa(
        source_manifest_path=case.manifest,
        market_hist_records_path=case.records,
        pre_match_path=case.pre_match,
        outcomes_path=case.outcomes,
        source_root=case.root,
    )
    assert report.overall_status == "PARTIAL_TOUR_ELIGIBILITY"
    statuses = {item.tour: item.status for item in report.tours}
    assert statuses == {
        "ATP": "ELIGIBLE_CONFIRMATORY",
        "WTA": "EXPLORATORY_ONLY_COVERAGE",
    }
    wta = next(item for item in report.tours if item.tour == "WTA")
    assert wta.gates.every_recent_year_close_coverage_at_least_50pct is False


def test_structural_source_hash_mismatch_blocks_qa(tmp_path: Path) -> None:
    case = _build_case(tmp_path, tamper_record_source_hash=True)
    report = run_market_hist_qa(
        source_manifest_path=case.manifest,
        market_hist_records_path=case.records,
        pre_match_path=case.pre_match,
        outcomes_path=case.outcomes,
        source_root=case.root,
    )
    assert report.structural_pass is False
    assert report.overall_status == "BLOCKED_STRUCTURAL"
    assert any("source_file_sha256" in error for error in report.structural_errors)


def test_checkpoint_provenance_mismatch_blocks_companion(
    eligible_case: QACase,
    tmp_path: Path,
) -> None:
    lines = eligible_case.records.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    earlier = next(
        item for item in first["checkpoints"] if item["checkpoint_name"] == "T-15M"
    )
    earlier["match_id"] = "wrong-match"
    lines[0] = json.dumps(first, sort_keys=True)
    altered = tmp_path / "altered.jsonl"
    altered.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bundle = build_market_hist_qa_bundle(
        source_manifest_path=eligible_case.manifest,
        market_hist_records_path=altered,
        pre_match_path=eligible_case.pre_match,
        outcomes_path=eligible_case.outcomes,
        source_root=eligible_case.root,
    )
    assert bundle.qa_report["structural_pass"] is True
    assert bundle.effective_overall_status == "BLOCKED_STRUCTURAL"
    assert any("match_id disagrees" in error for error in bundle.companion_structural_errors)
    assert bundle.checkpoint_coverage == ()
