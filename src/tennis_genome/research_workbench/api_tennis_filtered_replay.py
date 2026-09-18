from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Literal, Self

from pydantic import field_validator, model_validator

from . import api_tennis_conservative_wta_shadow
from .api_tennis_dynamic_shadow import (
    SHADOW_MODEL_ID,
    ApiTennisDynamicShadowBatch,
    build_api_tennis_dynamic_shadow_batch,
)
from .api_tennis_enrichment import (
    ApiTennisEnrichmentBatch,
    build_api_tennis_enrichment_batch,
)
from .contracts import WorkbenchRecord

REPLAY_ID = "API-TENNIS-FILTERED-SHADOW-REPLAY-001"


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ApiTennisFilteredReplayScore(WorkbenchRecord):
    replay_id: Literal["API-TENNIS-FILTERED-SHADOW-REPLAY-001"] = REPLAY_ID
    model_id: Literal["TGE-SHADOW-API-TENNIS-DYNAMIC-SR-V1"] = SHADOW_MODEL_ID
    event_key: int
    event_date: str
    tour: Literal["ATP", "WTA"]
    player_a_key: int
    player_b_key: int
    probability_a_match: float
    winner_side: Literal["A", "B"]
    correct: int
    brier: float
    log_loss: float
    prior_serve_points_a: int
    prior_serve_points_b: int
    prior_return_points_a: int
    prior_return_points_b: int
    any_history: bool
    both_players_history: bool
    source_raw_match_sha256: str

    @field_validator("probability_a_match")
    @classmethod
    def _probability(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("probability_a_match must be in [0, 1]")
        return value

    @field_validator("correct")
    @classmethod
    def _correct(cls, value: int) -> int:
        if value not in {0, 1}:
            raise ValueError("correct must be 0 or 1")
        return value

    @field_validator("brier", "log_loss")
    @classmethod
    def _finite_score(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("scores must be finite and non-negative")
        return value


class ApiTennisFilteredReplaySummary(WorkbenchRecord):
    replay_id: Literal["API-TENNIS-FILTERED-SHADOW-REPLAY-001"] = REPLAY_ID
    model_id: Literal["TGE-SHADOW-API-TENNIS-DYNAMIC-SR-V1"] = SHADOW_MODEL_ID
    source_raw_atp_sha256: str
    source_raw_wta_sha256: str
    source_pair_sha256: str
    daily_batch_count: int
    source_fixture_count: int
    admitted_match_count: int
    excluded_match_count: int
    all_accuracy: float
    all_brier: float
    all_log_loss: float
    any_history_count: int
    any_history_accuracy: float | None
    any_history_brier: float | None
    any_history_log_loss: float | None
    both_players_history_count: int
    both_players_history_accuracy: float | None
    both_players_history_brier: float | None
    both_players_history_log_loss: float | None
    conservative_wta_challenger_id: Literal[
        "TGE-CHALLENGER-WTA-DYNAMIC-SR-SHRUNK-V1"
    ] = api_tennis_conservative_wta_shadow.CHALLENGER_ID
    conservative_wta_min_prior_points: int = api_tennis_conservative_wta_shadow.MIN_PRIOR_POINTS_PER_PLAYER
    conservative_wta_shrinkage_to_neutral: float = api_tennis_conservative_wta_shadow.SHRINKAGE_TO_NEUTRAL
    conservative_wta_count: int
    conservative_wta_accuracy: float | None
    conservative_wta_brier: float | None
    conservative_wta_log_loss: float | None
    conservative_wta_event_keys: tuple[int, ...]
    daily_batch_semantic_sha256: tuple[str, ...]
    shadow_batch_semantic_sha256: str
    scores: tuple[ApiTennisFilteredReplayScore, ...]

    @field_validator(
        "source_raw_atp_sha256",
        "source_raw_wta_sha256",
        "source_pair_sha256",
        "shadow_batch_semantic_sha256",
    )
    @classmethod
    def _hash(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _validate_cardinality(self) -> Self:
        if self.admitted_match_count != len(self.scores):
            raise ValueError("admitted_match_count must equal score cardinality")
        if self.source_fixture_count != self.admitted_match_count + self.excluded_match_count:
            raise ValueError("source fixture accounting mismatch")
        if self.daily_batch_count != len(self.daily_batch_semantic_sha256):
            raise ValueError("daily batch hash cardinality mismatch")
        if self.any_history_count > self.admitted_match_count:
            raise ValueError("any_history_count exceeds admitted count")
        if self.both_players_history_count > self.any_history_count:
            raise ValueError("both-player history cannot exceed any-history count")
        if self.conservative_wta_count != len(self.conservative_wta_event_keys):
            raise ValueError("conservative WTA count must equal event-key cardinality")
        if self.conservative_wta_count > self.admitted_match_count:
            raise ValueError("conservative WTA count exceeds admitted count")
        if len(self.conservative_wta_event_keys) != len(
            set(self.conservative_wta_event_keys)
        ):
            raise ValueError("conservative WTA event keys must be unique")
        if self.conservative_wta_min_prior_points != api_tennis_conservative_wta_shadow.MIN_PRIOR_POINTS_PER_PLAYER:
            raise ValueError("conservative WTA history threshold drifted")
        if self.conservative_wta_shrinkage_to_neutral != api_tennis_conservative_wta_shadow.SHRINKAGE_TO_NEUTRAL:
            raise ValueError("conservative WTA shrinkage drifted")
        return self


def _parse_payload(raw: bytes) -> list[dict[str, object]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("filtered source must be UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("success") not in {1, "1"}:
        raise ValueError("filtered source did not report success")
    rows = payload.get("result")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("filtered source result must be an array of objects")
    return [dict(row) for row in rows]


def build_filtered_daily_enrichment_batches(
    *,
    raw_atp: bytes,
    raw_wta: bytes,
) -> tuple[ApiTennisEnrichmentBatch, ...]:
    """Derive deterministic daily research batches from retained filtered responses.

    The daily payloads are internal slices of already-retained provider evidence.
    Their hashes identify the exact derived slice; the replay summary separately
    retains the original ATP/WTA response hashes.
    """

    rows = _parse_payload(raw_atp) + _parse_payload(raw_wta)
    by_date: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    seen_event_keys: set[int] = set()
    for row in rows:
        event_key = row.get("event_key")
        if isinstance(event_key, bool) or not isinstance(event_key, int):
            raise ValueError("filtered fixture event_key must be an integer")
        if event_key in seen_event_keys:
            raise ValueError("duplicate event_key across retained filtered responses")
        seen_event_keys.add(event_key)
        event_date = row.get("event_date")
        if not isinstance(event_date, str) or not event_date:
            raise ValueError("filtered fixture event_date is required")
        by_date[event_date].append(row)

    batches: list[ApiTennisEnrichmentBatch] = []
    for requested_date in sorted(by_date):
        daily_payload = {
            "success": 1,
            "result": sorted(
                by_date[requested_date],
                key=lambda row: int(row["event_key"]),
            ),
        }
        batch = build_api_tennis_enrichment_batch(
            _canonical_json_bytes(daily_payload),
            requested_date=requested_date,
        )
        batches.append(batch)
    return tuple(batches)


def _metric_rows(
    rows: list[ApiTennisFilteredReplayScore],
) -> tuple[int, float | None, float | None, float | None]:
    if not rows:
        return 0, None, None, None
    count = len(rows)
    return (
        count,
        sum(row.correct for row in rows) / count,
        sum(row.brier for row in rows) / count,
        sum(row.log_loss for row in rows) / count,
    )


def replay_api_tennis_filtered_shadow(
    *,
    raw_atp: bytes,
    raw_wta: bytes,
) -> ApiTennisFilteredReplaySummary:
    batches = list(
        build_filtered_daily_enrichment_batches(
            raw_atp=raw_atp,
            raw_wta=raw_wta,
        )
    )
    if not batches:
        raise ValueError("filtered replay requires at least one daily batch")

    shadow: ApiTennisDynamicShadowBatch = build_api_tennis_dynamic_shadow_batch(batches)
    outcomes = {
        record.event_key: record.winner_side
        for batch in batches
        for record in batch.admitted_records
    }
    if len(outcomes) != shadow.record_count:
        raise ValueError("shadow/outcome cardinality mismatch")

    scores: list[ApiTennisFilteredReplayScore] = []
    epsilon = 1e-15
    for record in shadow.records:
        winner_side = outcomes.get(record.event_key)
        if winner_side is None:
            raise ValueError("missing outcome for shadow record")
        target = 1.0 if winner_side == "A" else 0.0
        probability = record.probability_a_match
        correct = int((probability >= 0.5) == (target == 1.0))
        clipped = min(max(probability, epsilon), 1.0 - epsilon)
        brier = (probability - target) ** 2
        log_loss = -(
            target * math.log(clipped)
            + (1.0 - target) * math.log(1.0 - clipped)
        )
        history_a = record.prior_serve_points_a + record.prior_return_points_a
        history_b = record.prior_serve_points_b + record.prior_return_points_b
        scores.append(
            ApiTennisFilteredReplayScore(
                event_key=record.event_key,
                event_date=record.event_date,
                tour=record.tour,
                player_a_key=record.player_a_key,
                player_b_key=record.player_b_key,
                probability_a_match=probability,
                winner_side=winner_side,
                correct=correct,
                brier=brier,
                log_loss=log_loss,
                prior_serve_points_a=record.prior_serve_points_a,
                prior_serve_points_b=record.prior_serve_points_b,
                prior_return_points_a=record.prior_return_points_a,
                prior_return_points_b=record.prior_return_points_b,
                any_history=history_a > 0 or history_b > 0,
                both_players_history=history_a > 0 and history_b > 0,
                source_raw_match_sha256=record.source_raw_match_sha256,
            )
        )

    all_count, all_accuracy, all_brier, all_log_loss = _metric_rows(scores)
    assert all_count > 0
    assert all_accuracy is not None and all_brier is not None and all_log_loss is not None

    any_history_rows = [row for row in scores if row.any_history]
    any_count, any_accuracy, any_brier, any_log_loss = _metric_rows(any_history_rows)
    both_rows = [row for row in scores if row.both_players_history]
    both_count, both_accuracy, both_brier, both_log_loss = _metric_rows(both_rows)

    conservative_rows: list[tuple[int, int, float, float]] = []
    for record in shadow.records:
        output = api_tennis_conservative_wta_shadow.build_conservative_wta_shadow_output(record)
        if output is None:
            continue
        winner_side = outcomes.get(record.event_key)
        if winner_side is None:
            raise ValueError("missing outcome for conservative WTA shadow record")
        target = 1.0 if winner_side == "A" else 0.0
        probability = output.p_player_a
        correct = int((probability >= 0.5) == (target == 1.0))
        clipped = min(max(probability, epsilon), 1.0 - epsilon)
        brier = (probability - target) ** 2
        log_loss = -(
            target * math.log(clipped)
            + (1.0 - target) * math.log(1.0 - clipped)
        )
        conservative_rows.append((record.event_key, correct, brier, log_loss))

    conservative_count = len(conservative_rows)
    if conservative_rows:
        conservative_accuracy = (
            sum(row[1] for row in conservative_rows) / conservative_count
        )
        conservative_brier = (
            sum(row[2] for row in conservative_rows) / conservative_count
        )
        conservative_log_loss = (
            sum(row[3] for row in conservative_rows) / conservative_count
        )
    else:
        conservative_accuracy = None
        conservative_brier = None
        conservative_log_loss = None

    source_fixture_count = len(_parse_payload(raw_atp)) + len(_parse_payload(raw_wta))
    pair_hash = _sha256(
        _canonical_json_bytes(
            {
                "raw_atp_sha256": _sha256(raw_atp),
                "raw_wta_sha256": _sha256(raw_wta),
            }
        )
    )
    return ApiTennisFilteredReplaySummary(
        source_raw_atp_sha256=_sha256(raw_atp),
        source_raw_wta_sha256=_sha256(raw_wta),
        source_pair_sha256=pair_hash,
        daily_batch_count=len(batches),
        source_fixture_count=source_fixture_count,
        admitted_match_count=len(scores),
        excluded_match_count=source_fixture_count - len(scores),
        all_accuracy=all_accuracy,
        all_brier=all_brier,
        all_log_loss=all_log_loss,
        any_history_count=any_count,
        any_history_accuracy=any_accuracy,
        any_history_brier=any_brier,
        any_history_log_loss=any_log_loss,
        both_players_history_count=both_count,
        both_players_history_accuracy=both_accuracy,
        both_players_history_brier=both_brier,
        both_players_history_log_loss=both_log_loss,
        conservative_wta_count=conservative_count,
        conservative_wta_accuracy=conservative_accuracy,
        conservative_wta_brier=conservative_brier,
        conservative_wta_log_loss=conservative_log_loss,
        conservative_wta_event_keys=tuple(row[0] for row in conservative_rows),
        daily_batch_semantic_sha256=tuple(batch.semantic_sha256 for batch in batches),
        shadow_batch_semantic_sha256=shadow.semantic_sha256,
        scores=tuple(scores),
    )
