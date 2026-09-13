from __future__ import annotations

from pathlib import Path

from tennis_genome.market.bookmaker_manifest import build_bookmaker_source_manifest


def test_manifest_excludes_post_2025_file_and_structurally_bad_wta_mirror(tmp_path: Path) -> None:
    valuebet = tmp_path / "valuebet"
    atp = tmp_path / "atp"
    wta = tmp_path / "wta"
    for root in (valuebet, atp, wta):
        root.mkdir()

    (valuebet / "valuebet-2025.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "1;2025-01-01 00:00:00;atp;Alpha A;Beta B;1.80;2.10\n",
        encoding="utf-8",
    )
    (valuebet / "valuebet-2026.csv").write_text(
        "match_id;date;genre;joueur1;joueur2;cote1_cloture;cote2_cloture\n"
        "2;2026-01-01 00:00:00;atp;Gamma G;Delta D;1.90;2.00\n",
        encoding="utf-8",
    )
    (wta / "wta-2024-corrupt.csv").write_text(
        "ATP,Date,Winner,Loser,PSW,PSL\n1,1/1/24,Alpha A,Beta B,1.80,2.10\n",
        encoding="utf-8",
    )

    manifest = build_bookmaker_source_manifest(
        valuebet_root=valuebet,
        tennis_data_atp_root=atp,
        tennis_data_wta_root=wta,
        requested_start_date="2021-01-01",
        requested_end_date="2025-12-31",
    )
    assert [item.relative_path for item in manifest.files] == ["valuebet-2025.csv"]
    excluded = {
        (item.root_key, item.relative_path): item.reason for item in manifest.excluded_files
    }
    assert excluded[("valuebetennis", "valuebet-2026.csv")] == "OUTSIDE_REQUESTED_INTERVAL"
    assert excluded[("tennis_data_wta", "wta-2024-corrupt.csv")] == "STRUCTURAL_INVALID"
