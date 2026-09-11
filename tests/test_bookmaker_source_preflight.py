from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.experiments.bookmaker_source_preflight import (
    run_bookmaker_source_preflight,
)
from tennis_genome.market.bookmaker_manifest import (
    build_bookmaker_source_manifest,
    write_bookmaker_source_manifest,
)


def _write_sources(root: Path) -> tuple[Path, Path, Path]:
    valuebet = root / "valuebet"
    atp = root / "atp"
    wta = root / "wta"
    valuebet.mkdir(parents=True)
    atp.mkdir()
    wta.mkdir()

    (valuebet / "valuebetennis-matchs-2025.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture;"
        "vainqueur_id;score;duree_min\n"
        "vb-atp;2025-03-01 12:00:00;atp;Alpha A;Beta B;1.80;2.10;1;6-4 6-4;80\n"
        "vb-wta;2025-03-02 12:00:00;wta;Gamma C;Delta D;1.95;;4;6-3 6-3;70\n",
        encoding="utf-8",
    )
    (atp / "atp_singles_results_2020.csv").write_text(
        "ATP,Date,Winner,Loser,PSW,PSL,Comment\n"
        "1,15/06/2020,Older Winner,Older Loser,1.70,2.20,Completed\n",
        encoding="utf-8",
    )
    (wta / "wta_singles_results_2020.csv").write_text(
        "WTA,Date,Winner,Loser,PSW,PSL,Comment\n"
        "1,16/06/2020,W Older Winner,W Older Loser,2.40,1.60,Completed\n",
        encoding="utf-8",
    )
    return valuebet, atp, wta


def _case(root: Path):
    valuebet, atp, wta = _write_sources(root)
    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2015-01-01",
        requested_end_date="2025-12-31",
    )
    manifest_path = root / "manifest.json"
    write_bookmaker_source_manifest(manifest, manifest_path)
    return manifest_path, valuebet, atp, wta


def test_source_preflight_is_outcome_blind_and_deterministic(tmp_path: Path) -> None:
    manifest, valuebet, atp, wta = _case(tmp_path)
    first = run_bookmaker_source_preflight(
        source_manifest_path=manifest,
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )
    second = run_bookmaker_source_preflight(
        source_manifest_path=manifest,
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
    )

    assert first == second
    assert first.outcome_blind is True
    assert first.confirmatory_result_free is True
    assert first.total_row_count == 4
    assert first.total_valid_quote_count == 3
    assert first.total_invalid_quote_count == 1
    assert first.tour_counts == {"ATP": 2, "WTA": 2}
    assert first.source_counts == {"TENNIS_DATA_UK": 2, "VALUEBETENNIS": 2}

    serialized = json.dumps(first.to_dict(), sort_keys=True).lower()
    for forbidden in ("vainqueur_id", "score", "duree_min", "winner", "loser", "a_won"):
        assert forbidden not in serialized


def test_source_preflight_rejects_source_mutation_after_manifest(tmp_path: Path) -> None:
    manifest, valuebet, atp, wta = _case(tmp_path)
    path = valuebet / "valuebetennis-matchs-2025.csv"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="size changed|hash changed"):
        run_bookmaker_source_preflight(
            source_manifest_path=manifest,
            valuebet_root=valuebet,
            tennis_data_atp_root=atp,
            tennis_data_wta_root=wta,
        )
