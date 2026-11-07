"""Commit a paper-only simple-logit challenger forecast from retained pre-match inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.calculator.io import load_matchup_input
from tennis_genome.data.canonical import PreMatchState
from tennis_genome.prospective.web_shadow import WebShadowFixture
from tennis_genome.research_workbench.simple_logit_challenger import (
    ChallengerExample,
    FrozenSimpleLogitChallenger,
)


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_shadow(
    *,
    artifact_path: Path,
    fixture_path: Path,
    matchup_path: Path,
    target_state_path: Path,
    champion_prediction_path: Path,
    source_run_id: int,
    source_artifact_id: int,
    output_path: Path,
    rank_evidence_path: Path | None = None,
    committed_at: datetime | None = None,
) -> dict[str, object]:
    if source_run_id <= 0 or source_artifact_id <= 0:
        raise ValueError("source run and artifact IDs must be positive")
    artifact_raw = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact = FrozenSimpleLogitChallenger.from_sealed_record(artifact_raw)
    fixture = WebShadowFixture(**json.loads(fixture_path.read_text(encoding="utf-8")))
    fixture.validate()
    matchup = load_matchup_input(matchup_path)
    state_raw = json.loads(target_state_path.read_text(encoding="utf-8"))
    state_raw["event_date"] = date.fromisoformat(state_raw["event_date"])
    state = PreMatchState(**state_raw)
    champion = json.loads(champion_prediction_path.read_text(encoding="utf-8"))

    scheduled = datetime.fromisoformat(fixture.scheduled_start)
    now = committed_at or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None or now >= scheduled:
        raise ValueError("challenger forecast must be committed before scheduled start")
    if artifact.tour != fixture.tour or state.tour != fixture.tour or matchup.tour != fixture.tour:
        raise ValueError("tour differs across retained input and challenger")
    if state.match_id != fixture.match_id or matchup.match_id != fixture.match_id:
        raise ValueError("fixture, state and matchup identify different matches")
    if state.event_date != scheduled.date() or matchup.foundational.event_date != scheduled.date():
        raise ValueError("target event dates differ from scheduled start")
    if (
        (state.player_a_id, state.player_b_id) != (matchup.player_a_id, matchup.player_b_id)
        or champion.get("player_a_id") != state.player_a_id
        or champion.get("player_b_id") != state.player_b_id
    ):
        raise ValueError("canonical player orientation differs")
    input_sha = _file_digest(matchup_path)
    if champion.get("input_manifest_sha256") != input_sha:
        raise ValueError("champion input hash differs from retained matchup")
    champion_fixture = champion.get("fixture")
    if (
        not isinstance(champion_fixture, dict)
        or champion_fixture.get("match_id") != fixture.match_id
        or champion_fixture.get("scheduled_start") != fixture.scheduled_start
    ):
        raise ValueError("champion fixture differs from retained target")
    unsigned_champion = dict(champion)
    champion_sha = unsigned_champion.pop("record_sha256", None)
    if _digest(unsigned_champion) != champion_sha:
        raise ValueError("champion prediction hash mismatch")
    champion_time = datetime.fromisoformat(champion["committed_at"])
    if champion_time > now or champion_time >= scheduled:
        raise ValueError("champion prediction chronology is invalid")
    if matchup.created_at > now or matchup.prediction_cutoff_at > now:
        raise ValueError("matchup input chronology is invalid")

    ranking_sha = None
    if artifact.include_rank:
        if rank_evidence_path is None:
            raise ValueError("RANK challenger requires retained ranking evidence")
        ranking = json.loads(rank_evidence_path.read_text(encoding="utf-8"))
        unsigned_ranking = dict(ranking)
        ranking_sha = unsigned_ranking.pop("record_sha256", None)
        if _digest(unsigned_ranking) != ranking_sha:
            raise ValueError("ranking evidence hash mismatch")
        if ranking.get("schema_version") != "simple-logit-retained-ranking-evidence-v1":
            raise ValueError("ranking evidence schema is unsupported")
        if ranking.get("production_eligible") is not False:
            raise ValueError("ranking evidence cannot claim production eligibility")
        if ranking.get("match_id") != fixture.match_id or (
            ranking.get("player_a_id"),
            ranking.get("player_b_id"),
        ) != (state.player_a_id, state.player_b_id):
            raise ValueError("ranking evidence identifies different players or match")
        if datetime.fromisoformat(ranking["observed_at_utc"]) >= min(now, scheduled):
            raise ValueError("ranking source was observed after prediction or scheduled start")
        players = ranking.get("players")
        if not isinstance(players, list) or len(players) != 2:
            raise ValueError("ranking evidence must bind exactly two players")
        if [row.get("canonical_player_id") for row in players] != [
            state.player_a_id,
            state.player_b_id,
        ] or [row.get("player_name") for row in players] != [
            state.player_a_name,
            state.player_b_name,
        ]:
            raise ValueError("ranking evidence player orientation differs")
        ranks = [int(row["rank"]) for row in players]
        points = [int(row["rank_points"]) for row in players]
        if any(value <= 0 for value in (*ranks, *points)):
            raise ValueError("ranking values must be positive")
        if any(
            value is not None
            for value in (state.rank_a, state.rank_b, state.rank_points_a, state.rank_points_b)
        ):
            raise ValueError("retained target state already contains ranking values")
        state = replace(
            state,
            rank_a=ranks[0],
            rank_b=ranks[1],
            rank_points_a=points[0],
            rank_points_b=points[1],
        )
    elif rank_evidence_path is not None:
        raise ValueError("BASE challenger must not consume ranking evidence")

    probability_a = artifact.predict_probability_a(
        ChallengerExample(snapshot=matchup.foundational, state=state)
    )
    record = {
        "schema_version": "simple-logit-paper-shadow-v1",
        "cohort": "PAPER_ONLY_STALE_HISTORY_CHALLENGER",
        "production_eligible": False,
        "formal_forward_eligible": False,
        "match_id": fixture.match_id,
        "tour": fixture.tour,
        "player_a_id": state.player_a_id,
        "player_b_id": state.player_b_id,
        "scheduled_start": scheduled.isoformat(),
        "committed_at": now.isoformat(),
        "source_run_id": source_run_id,
        "source_artifact_id": source_artifact_id,
        "source_matchup_sha256": input_sha,
        "source_target_state_sha256": _file_digest(target_state_path),
        "source_fixture_sha256": _file_digest(fixture_path),
        "champion_prediction_sha256": champion_sha,
        "challenger_artifact_sha256": artifact_raw["semantic_sha256"],
        "challenger_arm": "RANK" if artifact.include_rank else "BASE",
        "p_player_a": probability_a,
        "p_player_b": 1.0 - probability_a,
        "history_limitation": "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02",
    }
    if ranking_sha is not None:
        record["ranking_evidence_sha256"] = ranking_sha
    record["record_sha256"] = _digest(record)
    data = json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        if output_path.read_text(encoding="utf-8") != data:
            raise ValueError("existing immutable challenger prediction differs")
    else:
        temporary = output_path.with_name(output_path.name + ".tmp")
        temporary.write_text(data, encoding="utf-8", newline="\n")
        temporary.replace(output_path)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--matchup", required=True, type=Path)
    parser.add_argument("--target-state", required=True, type=Path)
    parser.add_argument("--champion-prediction", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True, type=int)
    parser.add_argument("--source-artifact-id", required=True, type=int)
    parser.add_argument("--rank-evidence", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            run_shadow(
                artifact_path=args.artifact,
                fixture_path=args.fixture,
                matchup_path=args.matchup,
                target_state_path=args.target_state,
                champion_prediction_path=args.champion_prediction,
                source_run_id=args.source_run_id,
                source_artifact_id=args.source_artifact_id,
                rank_evidence_path=args.rank_evidence,
                output_path=args.output,
            ),
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
