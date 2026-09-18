from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Literal, Self

from pydantic import field_validator, model_validator

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.ratings.dynamic_serve_return import walk_forward_dynamic_serve_return
from tennis_genome.simulation.tennis import point_sim_match_probability

from .api_tennis_enrichment import ApiTennisEnrichmentBatch, ApiTennisMatchEnrichment
from .api_tennis_matchstats_bridge import api_tennis_enrichment_to_match_stats
from .contracts import WorkbenchRecord

SHADOW_MODEL_ID = "TGE-SHADOW-API-TENNIS-DYNAMIC-SR-V1"


def _canonical_sha256(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ApiTennisDynamicShadowRecord(WorkbenchRecord):
    model_id: Literal["TGE-SHADOW-API-TENNIS-DYNAMIC-SR-V1"] = SHADOW_MODEL_ID
    match_id: str
    event_key: int
    event_date: str
    tour: Literal["ATP", "WTA"]
    player_a_key: int
    player_b_key: int
    player_a_name: str
    player_b_name: str
    probability_a_serve_point: float
    probability_b_serve_point: float
    probability_a_match: float
    prior_serve_points_a: int
    prior_serve_points_b: int
    prior_return_points_a: int
    prior_return_points_b: int
    source_raw_match_sha256: str

    @field_validator(
        "probability_a_serve_point",
        "probability_b_serve_point",
        "probability_a_match",
    )
    @classmethod
    def _probability(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("probabilities must be in [0, 1]")
        return value

    @field_validator("source_raw_match_sha256")
    @classmethod
    def _source_hash(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("source_raw_match_sha256 must be lowercase SHA-256")
        return value


class ApiTennisDynamicShadowBatch(WorkbenchRecord):
    model_id: Literal["TGE-SHADOW-API-TENNIS-DYNAMIC-SR-V1"] = SHADOW_MODEL_ID
    source_batch_sha256: str
    record_count: int
    records: tuple[ApiTennisDynamicShadowRecord, ...]

    @field_validator("source_batch_sha256")
    @classmethod
    def _source_hash(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("source_batch_sha256 must be lowercase SHA-256")
        return value

    @field_validator("record_count")
    @classmethod
    def _record_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("record_count must be non-negative")
        return value

    @model_validator(mode="after")
    def _cardinality(self) -> Self:
        if self.record_count != len(self.records):
            raise ValueError("record_count must equal records cardinality")
        match_ids = [record.match_id for record in self.records]
        if len(match_ids) != len(set(match_ids)):
            raise ValueError("shadow records must have unique match_id values")
        return self


def api_tennis_enrichment_to_historical_match(
    record: ApiTennisMatchEnrichment,
    *,
    source_order: int,
) -> HistoricalMatch:
    match_id = f"api-tennis:{record.event_key}"
    pre_match = PreMatchState(
        match_id=match_id,
        tour=record.tour,
        event_date=date.fromisoformat(record.event_date),
        source_order=source_order,
        tournament_id=f"api-tennis-tournament:{record.tournament_key}",
        tournament_name=record.tournament_name,
        tournament_level=None,
        surface="Unknown",
        round=record.tournament_round or None,
        best_of=3,
        player_a_id=f"api-tennis-player:{record.player_a_key}",
        player_b_id=f"api-tennis-player:{record.player_b_key}",
        player_a_name=record.player_a_name,
        player_b_name=record.player_b_name,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
    )
    outcome = MatchOutcome(
        match_id=match_id,
        a_won=record.winner_side == "A",
        score=None,
        retirement=False,
        walkover=False,
    )
    return HistoricalMatch(
        pre_match=pre_match,
        outcome=outcome,
        stats=api_tennis_enrichment_to_match_stats(record),
    )


def build_api_tennis_dynamic_shadow_batch(
    batches: list[ApiTennisEnrichmentBatch],
) -> ApiTennisDynamicShadowBatch:
    """Build chronological shadow probabilities from admitted API-Tennis evidence.

    API-Tennis scheduled clock times are intentionally ignored. Records are ordered
    only by source date and event key, while the dynamic serve/return engine treats
    each date as an atomic batch. This prevents within-date ordering from becoming
    a false proxy for actual match chronology.
    """

    if not batches:
        raise ValueError("at least one API-Tennis enrichment batch is required")

    by_event_key: dict[int, ApiTennisMatchEnrichment] = {}
    source_hashes: list[str] = []
    for batch in batches:
        source_hashes.append(batch.semantic_sha256)
        for record in batch.admitted_records:
            prior = by_event_key.get(record.event_key)
            if prior is not None:
                if prior.semantic_sha256 != record.semantic_sha256:
                    raise ValueError("conflicting API-Tennis event_key across batches")
                continue
            by_event_key[record.event_key] = record

    ordered_records = sorted(
        by_event_key.values(),
        key=lambda record: (record.event_date, record.event_key),
    )
    matches = [
        api_tennis_enrichment_to_historical_match(record, source_order=index)
        for index, record in enumerate(ordered_records)
    ]
    snapshots = walk_forward_dynamic_serve_return(matches)
    snapshot_by_match = {snapshot.match_id: snapshot for snapshot in snapshots}
    if len(snapshot_by_match) != len(matches):
        raise ValueError("dynamic serve/return snapshot cardinality mismatch")

    output: list[ApiTennisDynamicShadowRecord] = []
    for record in ordered_records:
        match_id = f"api-tennis:{record.event_key}"
        snapshot = snapshot_by_match.get(match_id)
        if snapshot is None:
            raise ValueError("missing dynamic serve/return snapshot")
        match_probability = point_sim_match_probability(
            snapshot.probability_a_serve_point,
            snapshot.probability_b_serve_point,
            best_of=3,
        )
        output.append(
            ApiTennisDynamicShadowRecord(
                match_id=match_id,
                event_key=record.event_key,
                event_date=record.event_date,
                tour=record.tour,
                player_a_key=record.player_a_key,
                player_b_key=record.player_b_key,
                player_a_name=record.player_a_name,
                player_b_name=record.player_b_name,
                probability_a_serve_point=snapshot.probability_a_serve_point,
                probability_b_serve_point=snapshot.probability_b_serve_point,
                probability_a_match=match_probability,
                prior_serve_points_a=snapshot.prior_serve_points_a,
                prior_serve_points_b=snapshot.prior_serve_points_b,
                prior_return_points_a=snapshot.prior_return_points_a,
                prior_return_points_b=snapshot.prior_return_points_b,
                source_raw_match_sha256=record.raw_match_sha256,
            )
        )

    combined_source_sha = _canonical_sha256(
        {
            "source_batch_semantic_sha256": sorted(source_hashes),
            "event_semantic_sha256": [record.semantic_sha256 for record in ordered_records],
        }
    )
    return ApiTennisDynamicShadowBatch(
        source_batch_sha256=combined_source_sha,
        record_count=len(output),
        records=tuple(output),
    )
