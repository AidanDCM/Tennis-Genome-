from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.market.bookmaker_batch import build_market_book_records
from tennis_genome.market.bookmaker_manifest import build_bookmaker_source_manifest


def _state(match_id: str, a: str, b: str) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=date(2025, 1, 1),
        source_order=1,
        tournament_id="t1",
        tournament_name="Test",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=f"{match_id}-a",
        player_b_id=f"{match_id}-b",
        player_a_name=a,
        player_b_name=b,
        rank_a=10,
        rank_b=20,
        rank_points_a=1000,
        rank_points_b=900,
    )


def _roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    valuebet = tmp_path / "valuebet"
    atp = tmp_path / "atp"
    wta = tmp_path / "wta"
    for path in (valuebet, atp, wta):
        path.mkdir()
    return valuebet, atp, wta


def test_valuebet_priority_and_tennis_data_fallback_are_deterministic(tmp_path: Path) -> None:
    valuebet, atp, wta = _roots(tmp_path)
    (valuebet / "valuebet-2025.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_ouverture;cote2_ouverture;"
        "cote1_cloture;cote2_cloture;vainqueur_id;score;duree_min\n"
        "1;2025-01-02 00:00:00;atp;Alpha A;Beta B;1.70;2.20;1.80;2.10;x;6-4;60\n"
        "2;2025-01-02 00:00:00;atp;Gamma G;Delta D;1.20;5.00;;;x;6-4;60\n",
        encoding="utf-8",
    )
    (atp / "atp-2025.csv").write_text(
        "ATP,Date,Winner,Loser,PSW,PSL,Comment\n"
        "1,2/1/25,Beta B,Alpha A,2.20,1.75,Completed\n"
        "1,2/1/25,Gamma G,Delta D,1.55,2.60,Completed\n",
        encoding="utf-8",
    )
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2025-01-01",
        requested_end_date="2025-12-31",
    )
    states = [_state("m1", "Alpha A", "Beta B"), _state("m2", "Gamma G", "Delta D")]
    records1, summary1 = build_market_book_records(
        manifest=manifest,
        pre_match_states=states,
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    records2, summary2 = build_market_book_records(
        manifest=manifest,
        pre_match_states=states,
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    assert records1 == records2
    assert summary1.output_sha256 == summary2.output_sha256

    selected = {
        record["join"]["match_id"]: record
        for record in records1
        if record["selected_primary"] is True
    }
    assert selected["m1"]["source_family"] == "VALUEBETENNIS"
    assert selected["m2"]["source_family"] == "TENNIS_DATA_UK"
    assert summary1.overlap_matches == 1
    assert all("score" not in record for record in records1)
    assert all("vainqueur_id" not in record for record in records1)


def test_conflicting_valuebet_quotes_fail_that_source_and_use_frozen_fallback(
    tmp_path: Path,
) -> None:
    valuebet, atp, wta = _roots(tmp_path)
    (valuebet / "valuebet-2025.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "1;2025-01-02 00:00:00;atp;Alpha A;Beta B;1.80;2.10\n"
        "2;2025-01-02 00:00:00;atp;Alpha A;Beta B;1.95;1.95\n",
        encoding="utf-8",
    )
    (atp / "atp-2025.csv").write_text(
        "ATP,Date,Winner,Loser,PSW,PSL\n1,2/1/25,Alpha A,Beta B,1.85,2.05\n",
        encoding="utf-8",
    )
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2025-01-01",
        requested_end_date="2025-12-31",
    )
    records, _ = build_market_book_records(
        manifest=manifest,
        pre_match_states=[_state("m1", "Alpha A", "Beta B")],
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    valuebet_records = [r for r in records if r["source_family"] == "VALUEBETENNIS"]
    assert len(valuebet_records) == 2
    assert all(r["source_conflict"] is True for r in valuebet_records)
    selected = [r for r in records if r["selected_primary"] is True]
    assert len(selected) == 1
    assert selected[0]["source_family"] == "TENNIS_DATA_UK"


def test_indexed_join_preserves_frozen_ambiguity_window(tmp_path: Path) -> None:
    valuebet, atp, wta = _roots(tmp_path)
    (valuebet / "valuebet-2025.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "1;2025-01-03 00:00:00;atp;Alpha A;Beta B;1.80;2.10\n",
        encoding="utf-8",
    )
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2025-01-01",
        requested_end_date="2025-12-31",
    )
    first = _state("m1", "Alpha A", "Beta B")
    second = replace(
        _state("m2", "Beta B", "Alpha A"),
        event_date=date(2025, 1, 7),
    )
    unrelated = _state("m3", "Gamma G", "Delta D")
    records, summary = build_market_book_records(
        manifest=manifest,
        pre_match_states=[unrelated, second, first],
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    assert len(records) == 1
    assert records[0]["join_status"] == "AMBIGUOUS"
    assert records[0]["candidate_match_ids"] == ["m1", "m2"]
    assert records[0]["join"] is None
    assert records[0]["selected_primary"] is False
    assert summary.selected_primary_quotes == 0
