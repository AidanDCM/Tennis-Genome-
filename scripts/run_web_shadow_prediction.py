from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.calculator.contract import load_validated_matchup_calculator
from tennis_genome.calculator.io import load_matchup_input
from tennis_genome.prospective.web_shadow import (
    WebShadowFixture,
    WebShadowPrediction,
    write_record,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_fixture(path: Path) -> WebShadowFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("fixture JSON must contain an object")
    fixture = WebShadowFixture(**raw)
    fixture.validate()
    return fixture


def run_web_shadow_prediction(
    *,
    fixture_path: Path,
    matchup_input_path: Path,
    bundle_path: Path,
    player_a_id: str,
    player_b_id: str,
    model_source_sha: str,
    output_path: Path,
    committed_at: datetime | None = None,
    calculator: object | None = None,
) -> dict[str, object]:
    fixture = _load_fixture(fixture_path)
    matchup = load_matchup_input(matchup_input_path)

    if fixture.tour != "WTA" or matchup.tour != "WTA":
        raise ValueError("web-shadow runner currently supports WTA only")
    if matchup.match_id != fixture.match_id:
        raise ValueError("matchup match_id differs from frozen web fixture")
    if matchup.player_a_id != player_a_id or matchup.player_b_id != player_b_id:
        raise ValueError("matchup player IDs differ from explicit frozen identity binding")
    if player_a_id == player_b_id:
        raise ValueError("frozen player IDs must be distinct")

    scheduled_start = datetime.fromisoformat(fixture.scheduled_start)
    if matchup.foundational.event_date != scheduled_start.date():
        raise ValueError("matchup event date differs from frozen fixture scheduled date")

    commit_time = committed_at or datetime.now(UTC)
    if commit_time.tzinfo is None or commit_time.utcoffset() is None:
        raise ValueError("committed_at must be timezone-aware")
    if matchup.prediction_cutoff_at > commit_time:
        raise ValueError("matchup prediction cutoff occurs after web-shadow commitment")
    if matchup.created_at > commit_time:
        raise ValueError("matchup creation occurs after web-shadow commitment")

    calculator = calculator or load_validated_matchup_calculator(bundle_path)
    calculation = calculator.calculate(matchup)

    if calculation.player_a_id != player_a_id or calculation.player_b_id != player_b_id:
        raise ValueError("calculator output identities differ from frozen identity binding")

    prediction = WebShadowPrediction(
        fixture=fixture,
        committed_at=commit_time.isoformat(),
        p_player_a=calculation.prediction.p_player_a,
        p_player_b=calculation.prediction.p_player_b,
        model_source_sha=model_source_sha,
        input_manifest_sha256=_sha256_file(matchup_input_path),
    ).record()
    prediction["player_a_id"] = player_a_id
    prediction["player_b_id"] = player_b_id
    prediction["production_bundle_sha256"] = calculation.production_bundle_sha256
    prediction["calculator_assessment_status"] = calculation.assessment_status

    unsigned = dict(prediction)
    unsigned.pop("record_sha256")
    prediction["record_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()

    write_record(output_path, prediction)
    return prediction


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an isolated, provider-free WTA web-shadow Genome prediction"
    )
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--matchup-input", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--player-a-id", required=True)
    parser.add_argument("--player-b-id", required=True)
    parser.add_argument("--model-source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--committed-at")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    committed_at = (
        None if args.committed_at is None else datetime.fromisoformat(args.committed_at)
    )
    result = run_web_shadow_prediction(
        fixture_path=args.fixture,
        matchup_input_path=args.matchup_input,
        bundle_path=args.bundle,
        player_a_id=args.player_a_id,
        player_b_id=args.player_b_id,
        model_source_sha=args.model_source_sha,
        output_path=args.output,
        committed_at=committed_at,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
