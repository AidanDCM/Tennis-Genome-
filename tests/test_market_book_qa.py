from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.experiments.market_book_qa import run_market_book_qa
from tennis_genome.market.bookmaker_manifest import (
    build_bookmaker_source_manifest,
    write_bookmaker_source_manifest,
)
from tennis_genome.market.odds import proportional_novig_two_way


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _make_case(
    root: Path, *, selection_rule=None
) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    valuebet = root / "valuebet"
    atp_root = root / "atp"
    wta_root = root / "wta"
    valuebet.mkdir(parents=True)
    atp_root.mkdir()
    wta_root.mkdir()

    raw_lines = [
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture;"
        "vainqueur_id;score;duree_min"
    ]
    pre_rows = []
    outcome_rows = []
    specs = []
    row_number = 2
    for tour in ("ATP", "WTA"):
        for year in range(2020, 2026):
            count = 1000 if year == 2020 else 100
            for idx in range(count):
                match_id = f"{tour.lower()}-{year}-{idx:04d}"
                player_a = f"A {tour} {year} {idx}"
                player_b = f"B {tour} {year} {idx}"
                raw_lines.append(
                    f"{match_id};{year}-06-15 00:00:00;{tour.lower()};{player_a};{player_b};"
                    "1.90;2.10;x;6-4;60"
                )
                pre_rows.append(
                    {
                        "match_id": match_id,
                        "tour": tour,
                        "event_date": date(year, 6, 15),
                    }
                )
                outcome_rows.append(
                    {"match_id": match_id, "retirement": False, "walkover": False}
                )
                specs.append((match_id, tour, year, player_a, player_b, row_number))
                row_number += 1
    source = valuebet / "valuebet.csv"
    source.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp_root,
        tennis_data_wta_root=wta_root,
        requested_start_date="2020-01-01",
        requested_end_date="2025-12-31",
    )
    manifest_path = root / "manifest.json"
    write_bookmaker_source_manifest(manifest, manifest_path)
    source_hash = manifest.files[0].sha256
    p_a, p_b = proportional_novig_two_way(1.90, 2.10)

    records = []
    for match_id, tour, year, player_a, player_b, source_row_number in specs:
        selected = True if selection_rule is None else bool(selection_rule(tour, year, match_id))
        sanitized_hash = _sha(f"sanitized:{match_id}")
        join_payload = {
            "resolver_version": "bookmaker-canonical-join-v1",
            "sanitized_row_hash": sanitized_hash,
            "match_id": match_id,
            "player_a_id": f"{match_id}-a",
            "player_b_id": f"{match_id}-b",
            "offset_days": 0,
            "days_before": 4,
            "days_after": 21,
        }
        join_hash = hashlib.sha256(_canonical_bytes(join_payload)).hexdigest()
        join = {
            "join_hash": join_hash,
            "resolver_version": "bookmaker-canonical-join-v1",
            "match_id": match_id,
            "tour": tour,
            "player_a_id": f"{match_id}-a",
            "player_b_id": f"{match_id}-b",
            "player_a_name": player_a,
            "player_b_name": player_b,
            "source_match_date": f"{year}-06-15",
            "tournament_date_offset_days": 0,
            "days_before_window": 4,
            "days_after_window": 21,
        }
        payload = {
            "batch_version": "market-book-001-batch-v1",
            "market_policy": "BOOKMAKER_CLOSE_V1",
            "source_family": "VALUEBETENNIS",
            "source_file": "valuebetennis/valuebet.csv",
            "source_file_sha256": source_hash,
            "source_row_number": source_row_number,
            "source_row_key": match_id,
            "sanitized_row_hash": sanitized_hash,
            "match_date": f"{year}-06-15",
            "tour": tour,
            "neutral_player_names": [player_a, player_b],
            "neutral_player_names_normalized": [player_a.lower(), player_b.lower()],
            "quote_valid": True,
            "join_status": "MATCHED",
            "candidate_match_ids": [match_id],
            "join": join,
            "decimal_odds_a": 1.90,
            "decimal_odds_b": 2.10,
            "raw_implied_probability_sum": (1 / 1.90) + (1 / 2.10),
            "overround": ((1 / 1.90) + (1 / 2.10)) - 1,
            "market_probability_a": p_a,
            "market_probability_b": p_b,
            "source_conflict": False,
            "duplicate_of_sanitized_row_hash": None,
            "selected_primary": selected,
            "selected_policy": "BOOKMAKER_CLOSE_V1" if selected else None,
        }
        records.append(
            {"record_hash": hashlib.sha256(_canonical_bytes(payload)).hexdigest(), **payload}
        )

    records_path = root / "records.jsonl"
    records_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    pre_path = root / "pre_match.parquet"
    outcomes_path = root / "outcomes.parquet"
    pd.DataFrame(pre_rows).to_parquet(pre_path, index=False)
    pd.DataFrame(outcome_rows).to_parquet(outcomes_path, index=False)
    return manifest_path, records_path, pre_path, outcomes_path, valuebet, atp_root, wta_root


def _run(case):
    manifest, records, pre, outcomes, valuebet, atp, wta = case
    return run_market_book_qa(
        source_manifest_path=manifest,
        market_book_records_path=records,
        pre_match_path=pre,
        outcomes_path=outcomes,
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )


def test_full_synthetic_case_is_confirmatory_eligible(tmp_path: Path) -> None:
    report = _run(_make_case(tmp_path))
    assert report.overall_status == "ELIGIBLE_CONFIRMATORY"
    assert all(tour.gates.passed for tour in report.tours)
    assert all(tour.prior_rows_before_2021 == 1000 for tour in report.tours)


def test_recent_year_below_50pct_fails_gate(tmp_path: Path) -> None:
    def rule(tour: str, year: int, match_id: str) -> bool:
        if tour == "WTA" and year == 2024:
            return int(match_id.rsplit("-", 1)[1]) < 49
        return True

    report = _run(_make_case(tmp_path, selection_rule=rule))
    wta = next(row for row in report.tours if row.tour == "WTA")
    assert report.overall_status == "INSUFFICIENT_COVERAGE"
    assert wta.gates.every_recent_year_close_coverage_at_least_50pct is False
    assert wta.gates.every_recent_year_at_least_100_rows is False


def test_prior_history_below_1000_fails_gate(tmp_path: Path) -> None:
    skipped = "atp-2020-0999"

    def rule(tour: str, year: int, match_id: str) -> bool:
        return match_id != skipped

    report = _run(_make_case(tmp_path, selection_rule=rule))
    atp = next(row for row in report.tours if row.tour == "ATP")
    assert atp.prior_rows_before_2021 == 999
    assert atp.gates.at_least_1000_prior_rows_before_first_evaluation_year is False


def test_tampered_record_hash_fails_structurally(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    records_path = case[1]
    lines = records_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["market_probability_a"] = 0.9
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    records_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="record hash mismatch"):
        _run(case)
