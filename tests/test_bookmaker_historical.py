from __future__ import annotations

from pathlib import Path

import pytest

from tennis_genome.market.providers.bookmaker_historical import (
    load_tennis_data_quotes,
    load_valuebetennis_quotes,
)


def test_valuebet_adapter_does_not_emit_outcomes_and_uses_closing_only(tmp_path: Path) -> None:
    path = tmp_path / "valuebet.csv"
    path.write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_ouverture;cote2_ouverture;"
        "cote1_cloture;cote2_cloture;vainqueur_id;score;duree_min\n"
        "1;2025-01-01 00:00:00;atp;Beta B;Alpha A;1.10;9.00;;;p2;6-0 6-0;40\n",
        encoding="utf-8",
    )
    quotes = load_valuebetennis_quotes(path)
    assert len(quotes) == 1
    quote = quotes[0]
    assert quote.neutral_player_1_normalized == "alpha a"
    assert quote.neutral_player_2_normalized == "beta b"
    assert quote.decimal_odds_1 is None
    assert quote.decimal_odds_2 is None
    assert quote.quote_valid is False
    payload = quote.to_dict()
    assert "vainqueur_id" not in payload
    assert "score" not in payload
    assert "duree_min" not in payload


def test_valuebet_unusable_identity_row_does_not_quarantine_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "valuebet.csv"
    path.write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "1;2023-05-01 00:00:00;atp;Alpha A;Beta B;1.80;2.10\n"
        "2;2023-05-02 00:00:00;atp;Unknown Player;Unknown Player;1.90;1.90\n"
        "3;2023-05-03 00:00:00;wta;Gamma C;Delta D;2.20;1.70\n",
        encoding="utf-8",
    )
    quotes = load_valuebetennis_quotes(path)
    assert [quote.source_row_key for quote in quotes] == ["1", "3"]
    assert all(quote.quote_valid for quote in quotes)


def test_valuebet_malformed_date_still_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "valuebet.csv"
    path.write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "1;not-a-date;atp;Alpha A;Beta B;1.80;2.10\n",
        encoding="utf-8",
    )
    with pytest.raises((ValueError, TypeError)):
        load_valuebetennis_quotes(path)


def test_tennis_data_winner_loser_orientation_is_neutralized(tmp_path: Path) -> None:
    path = tmp_path / "atp.csv"
    path.write_text(
        "ATP,Date,Winner,Loser,PSW,PSL,Comment,W1,L1\n"
        "1,1/1/23,Beta B,Alpha A,2.50,1.60,Completed,6,4\n"
        "1,1/1/23,Alpha A,Beta B,1.60,2.50,Completed,6,4\n",
        encoding="utf-8",
    )
    quotes = load_tennis_data_quotes(path, tour="ATP")
    assert len(quotes) == 2
    first, second = quotes
    assert first.neutral_player_1_normalized == second.neutral_player_1_normalized == "alpha a"
    assert first.neutral_player_2_normalized == second.neutral_player_2_normalized == "beta b"
    assert first.decimal_odds_1 == second.decimal_odds_1 == 1.60
    assert first.decimal_odds_2 == second.decimal_odds_2 == 2.50
    for payload in (first.to_dict(), second.to_dict()):
        assert "Winner" not in payload
        assert "Loser" not in payload
        assert "Comment" not in payload


def test_tennis_data_iso_date_is_not_reinterpreted_day_first(tmp_path: Path) -> None:
    path = tmp_path / "wta.csv"
    path.write_text(
        "WTA,Date,Winner,Loser,PSW,PSL\n1,2021-02-01,Cornet A.,Tomljanovic A.,1.80,2.10\n",
        encoding="utf-8",
    )
    quotes = load_tennis_data_quotes(path, tour="WTA")
    assert len(quotes) == 1
    assert quotes[0].match_date.isoformat() == "2021-02-01"
    assert quotes[0].source_row_key == "2021-02-01:2"


def test_tennis_data_legacy_non_iso_date_remains_day_first(tmp_path: Path) -> None:
    path = tmp_path / "wta.csv"
    path.write_text(
        "WTA,Date,Winner,Loser,PSW,PSL\n1,3/2/21,Alpha A,Beta B,1.80,2.10\n",
        encoding="utf-8",
    )
    quotes = load_tennis_data_quotes(path, tour="WTA")
    assert len(quotes) == 1
    assert quotes[0].match_date.isoformat() == "2021-02-03"


def test_tennis_data_malformed_date_still_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "wta.csv"
    path.write_text(
        "WTA,Date,Winner,Loser,PSW,PSL\n1,not-a-date,Alpha A,Beta B,1.80,2.10\n",
        encoding="utf-8",
    )
    with pytest.raises((ValueError, TypeError)):
        load_tennis_data_quotes(path, tour="WTA")


def test_tennis_data_tour_marker_mismatch_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "bad_wta_2024.csv"
    path.write_text(
        "ATP,Date,Winner,Loser,PSW,PSL\n1,1/1/24,Alpha A,Beta B,1.80,2.10\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tour marker"):
        load_tennis_data_quotes(path, tour="WTA")
