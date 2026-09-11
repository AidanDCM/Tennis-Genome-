from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.market.bookmaker_alias import tennis_data_name_matches_canonical
from tennis_genome.market.bookmaker_batch_v2 import build_market_book_records
from tennis_genome.market.bookmaker_manifest import build_bookmaker_source_manifest


@pytest.mark.parametrize(
    ("source", "canonical"),
    [
        ("Dimitrov G.", "Grigor Dimitrov"),
        ("De Minaur A.", "Alex De Minaur"),
        ("Barrios Vera M.T.", "Marcelo Tomas Barrios Vera"),
        ("Badosa P.", "Paula Badosa Gibert"),
        ("Badosa Gibert P.", "Paula Badosa Gibert"),
        ("Aragone JC", "JC Aragone"),
        ("Wang Xiyu", "Xiyu Wang"),
    ],
)
def test_frozen_tennis_data_alias_examples(source: str, canonical: str) -> None:
    assert tennis_data_name_matches_canonical(source, canonical)


def test_wrong_initial_does_not_alias() -> None:
    assert not tennis_data_name_matches_canonical("Dimitrov A.", "Grigor Dimitrov")


def _state(match_id: str, a: str, b: str, *, event_date: date = date(2025, 1, 1)) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=1,
        tournament_id=f"t-{match_id}",
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


def test_tennis_data_alias_preserves_price_orientation_and_no_outcome_fields(tmp_path: Path) -> None:
    valuebet, atp, wta = _roots(tmp_path)
    (atp / "atp-2025.csv").write_text(
        "ATP,Date,Winner,Loser,PSW,PSL,Comment\n"
        "1,2/1/25,Nishioka Y.,Dimitrov G.,2.50,1.60,Completed\n",
        encoding="utf-8",
    )
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2025-01-01",
        requested_end_date="2025-12-31",
    )
    records, summary = build_market_book_records(
        manifest=manifest,
        pre_match_states=[_state("m1", "Grigor Dimitrov", "Yoshihito Nishioka")],
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    assert summary.batch_version == "market-book-001-batch-v2"
    assert summary.selected_by_source == {"TENNIS_DATA_UK": 1}
    selected = next(record for record in records if record["selected_primary"] is True)
    assert selected["join"]["resolver_version"] == "bookmaker-canonical-join-v2"
    assert selected["join"]["match_id"] == "m1"
    assert selected["decimal_odds_a"] == pytest.approx(1.60)
    assert selected["decimal_odds_b"] == pytest.approx(2.50)
    assert "Winner" not in selected
    assert "Loser" not in selected
    assert "Comment" not in selected


def test_alias_resolution_fails_closed_when_two_matches_fit_window(tmp_path: Path) -> None:
    valuebet, atp, wta = _roots(tmp_path)
    (atp / "atp-2025.csv").write_text(
        "ATP,Date,Winner,Loser,PSW,PSL\n"
        "1,3/1/25,Dimitrov G.,Nishioka Y.,1.60,2.50\n",
        encoding="utf-8",
    )
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2025-01-01",
        requested_end_date="2025-12-31",
    )
    first = _state("m1", "Grigor Dimitrov", "Yoshihito Nishioka")
    second = replace(first, match_id="m2", event_date=date(2025, 1, 7))
    records, summary = build_market_book_records(
        manifest=manifest,
        pre_match_states=[first, second],
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    assert records[0]["join_status"] == "AMBIGUOUS"
    assert records[0]["candidate_match_ids"] == ["m1", "m2"]
    assert records[0]["selected_primary"] is False
    assert summary.selected_primary_quotes == 0


def test_valuebet_exact_priority_is_unchanged_in_v2(tmp_path: Path) -> None:
    valuebet, atp, wta = _roots(tmp_path)
    (valuebet / "valuebet-2025.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "1;2025-01-02 00:00:00;atp;Grigor Dimitrov;Yoshihito Nishioka;1.70;2.30\n",
        encoding="utf-8",
    )
    (atp / "atp-2025.csv").write_text(
        "ATP,Date,Winner,Loser,PSW,PSL\n"
        "1,2/1/25,Dimitrov G.,Nishioka Y.,1.60,2.50\n",
        encoding="utf-8",
    )
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2025-01-01",
        requested_end_date="2025-12-31",
    )
    records, summary = build_market_book_records(
        manifest=manifest,
        pre_match_states=[_state("m1", "Grigor Dimitrov", "Yoshihito Nishioka")],
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    selected = [record for record in records if record["selected_primary"] is True]
    assert len(selected) == 1
    assert selected[0]["source_family"] == "VALUEBETENNIS"
    assert summary.overlap_matches == 1
