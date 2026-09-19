from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from scripts.build_web_shadow_local_input import build_local_web_shadow_matchup
from scripts.build_web_shadow_target_state import build_web_shadow_target_state
from scripts.run_web_shadow_prediction import run_web_shadow_prediction


def _load_slate(path: Path) -> list[Path]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("slate JSON must contain an object")
    values = raw.get("fixture_paths")
    if not isinstance(values, list) or not values:
        raise ValueError("slate fixture_paths must be a non-empty list")
    fixtures: list[Path] = []
    seen: set[str] = set()
    for value in values:
        fixture = Path(str(value))
        if fixture.is_absolute() or ".." in fixture.parts:
            raise ValueError("fixture paths must be repository-relative")
        if fixture.parts[:2] != ("web-shadow", "fixtures"):
            raise ValueError("fixture paths must be under web-shadow/fixtures/")
        key = fixture.as_posix()
        if key in seen:
            raise ValueError(f"duplicate fixture path in slate: {key}")
        if not fixture.is_file():
            raise FileNotFoundError(f"fixture is missing: {fixture}")
        seen.add(key)
        fixtures.append(fixture)
    return fixtures


def run_web_shadow_slate(
    *,
    slate_path: Path,
    registry_path: Path,
    base_dir: Path,
    bundle_path: Path,
    model_source_sha: str,
    output_root: Path,
    history_mode: str = "FROZEN_LOCAL_HISTORY_ONLY",
    expected_history_max_date: date | None = None,
) -> dict[str, object]:
    fixtures = _load_slate(slate_path)
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    used_stems: set[str] = set()

    for fixture_path in fixtures:
        stem = fixture_path.stem
        if stem in used_stems:
            raise ValueError(f"duplicate fixture filename stem in slate: {stem}")
        used_stems.add(stem)
        match_root = output_root / "matches" / stem
        target_state_path = match_root / "target-state.json"
        normalized_fixture_path = match_root / "normalized-fixture.json"
        matchup_input_path = match_root / "matchup-input.json"
        input_manifest_path = match_root / "local-input-manifest.json"
        prediction_path = match_root / "prediction.json"

        try:
            target = build_web_shadow_target_state(
                fixture_path=fixture_path,
                registry_path=registry_path,
                target_state_path=target_state_path,
                normalized_fixture_path=normalized_fixture_path,
            )
            manifest = build_local_web_shadow_matchup(
                fixture_path=normalized_fixture_path,
                target_state_path=target_state_path,
                base_dir=base_dir,
                output_path=matchup_input_path,
                manifest_path=input_manifest_path,
                history_mode=history_mode,
                expected_history_max_date=expected_history_max_date,
            )
            prediction = run_web_shadow_prediction(
                fixture_path=normalized_fixture_path,
                matchup_input_path=matchup_input_path,
                bundle_path=bundle_path,
                player_a_id=str(target["player_a_id"]),
                player_b_id=str(target["player_b_id"]),
                model_source_sha=model_source_sha,
                output_path=prediction_path,
                committed_at=datetime.now(UTC),
            )
        except (ValueError, RuntimeError, FileNotFoundError, StopIteration) as exc:
            skipped.append(
                {
                    "fixture_path": fixture_path.as_posix(),
                    "artifact_stem": stem,
                    "reason_type": type(exc).__name__,
                    "reason": str(exc),
                }
            )
            continue

        results.append(
            {
                "fixture_path": fixture_path.as_posix(),
                "artifact_stem": stem,
                "match_id": prediction["fixture"]["match_id"],
                "scheduled_start": prediction["fixture"]["scheduled_start"],
                "selected_player": prediction["selected_player"],
                "p_player_a": prediction["p_player_a"],
                "p_player_b": prediction["p_player_b"],
                "prediction_record_sha256": prediction["record_sha256"],
                "target_history_match_counts": manifest[
                    "target_history_match_counts"
                ],
                "minimum_point_exposure": manifest["minimum_point_exposure"],
                "prediction_path": prediction_path.as_posix(),
            }
        )

    summary: dict[str, object] = {
        "schema_version": "tennis-genome-web-shadow-slate-v1",
        "production_eligible": False,
        "history_mode": history_mode,
        "eligible_target_count": len(fixtures),
        "predicted_target_count": len(results),
        "skipped_target_count": len(skipped),
        "results": results,
        "skipped_targets": skipped,
    }
    if len(results) + len(skipped) != len(fixtures):
        raise RuntimeError("predicted + skipped differs from Web Shadow slate denominator")

    (output_root / "slate-manifest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a provider-free Web Shadow slate against one frozen WTA history"
    )
    parser.add_argument("--slate", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--model-source-sha", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--history-mode",
        default="FROZEN_LOCAL_HISTORY_ONLY",
    )
    parser.add_argument("--expected-history-max-date")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run_web_shadow_slate(
        slate_path=args.slate,
        registry_path=args.registry,
        base_dir=args.base_dir,
        bundle_path=args.bundle,
        model_source_sha=args.model_source_sha,
        output_root=args.output_root,
        history_mode=args.history_mode,
        expected_history_max_date=(
            None
            if args.expected_history_max_date is None
            else date.fromisoformat(args.expected_history_max_date)
        ),
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
