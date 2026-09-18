from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_filtered_replay import (
    replay_api_tennis_filtered_shadow,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay retained filtered API-Tennis evidence through the dynamic SR shadow"
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    raw_atp = (args.source_dir / "raw-atp-fixtures.json").read_bytes()
    raw_wta = (args.source_dir / "raw-wta-fixtures.json").read_bytes()
    replay = replay_api_tennis_filtered_shadow(raw_atp=raw_atp, raw_wta=raw_wta)

    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "replay.json").write_text(
        json.dumps(replay.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "replay_semantic_sha256": replay.semantic_sha256,
                "source_raw_atp_sha256": replay.source_raw_atp_sha256,
                "source_raw_wta_sha256": replay.source_raw_wta_sha256,
                "source_pair_sha256": replay.source_pair_sha256,
                "shadow_batch_semantic_sha256": replay.shadow_batch_semantic_sha256,
                "daily_batch_count": replay.daily_batch_count,
                "source_fixture_count": replay.source_fixture_count,
                "admitted_match_count": replay.admitted_match_count,
                "excluded_match_count": replay.excluded_match_count,
                "any_history_count": replay.any_history_count,
                "both_players_history_count": replay.both_players_history_count,
                "conservative_wta_challenger_id": replay.conservative_wta_challenger_id,
                "conservative_wta_min_prior_points": replay.conservative_wta_min_prior_points,
                "conservative_wta_shrinkage_to_neutral": (
                    replay.conservative_wta_shrinkage_to_neutral
                ),
                "conservative_wta_count": replay.conservative_wta_count,
                "conservative_wta_accuracy": replay.conservative_wta_accuracy,
                "conservative_wta_brier": replay.conservative_wta_brier,
                "conservative_wta_log_loss": replay.conservative_wta_log_loss,
                "development_only": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "replay_id": replay.replay_id,
                "model_id": replay.model_id,
                "replay_semantic_sha256": replay.semantic_sha256,
                "admitted_match_count": replay.admitted_match_count,
                "excluded_match_count": replay.excluded_match_count,
                "all_accuracy": replay.all_accuracy,
                "all_brier": replay.all_brier,
                "all_log_loss": replay.all_log_loss,
                "any_history_count": replay.any_history_count,
                "any_history_accuracy": replay.any_history_accuracy,
                "any_history_brier": replay.any_history_brier,
                "any_history_log_loss": replay.any_history_log_loss,
                "both_players_history_count": replay.both_players_history_count,
                "both_players_history_accuracy": replay.both_players_history_accuracy,
                "both_players_history_brier": replay.both_players_history_brier,
                "both_players_history_log_loss": replay.both_players_history_log_loss,
                "conservative_wta_challenger_id": replay.conservative_wta_challenger_id,
                "conservative_wta_min_prior_points": replay.conservative_wta_min_prior_points,
                "conservative_wta_shrinkage_to_neutral": (
                    replay.conservative_wta_shrinkage_to_neutral
                ),
                "conservative_wta_count": replay.conservative_wta_count,
                "conservative_wta_accuracy": replay.conservative_wta_accuracy,
                "conservative_wta_brier": replay.conservative_wta_brier,
                "conservative_wta_log_loss": replay.conservative_wta_log_loss,
                "development_only": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
