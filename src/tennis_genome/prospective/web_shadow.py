from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

WEB_SHADOW_SCHEMA = "tennis-genome-web-shadow-v1"
_ALLOWED_STATUSES = {"SCHEDULED", "COMPLETED", "RETIREMENT", "WALKOVER", "DEFAULTED"}


def _parse_time(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class WebShadowFixture:
    match_id: str
    tour: str
    tournament: str
    round: str
    surface: str
    scheduled_start: str
    player_a: str
    player_b: str
    source_url: str
    source_observed_at: str
    tournament_id: str = ""
    tournament_level: str = ""

    def validate(self) -> None:
        required_fields = (
            "match_id",
            "tour",
            "tournament",
            "round",
            "surface",
            "player_a",
            "player_b",
            "source_url",
        )
        for name in required_fields:
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.player_a == self.player_b:
            raise ValueError("fixture players must be distinct")
        scheduled = _parse_time(self.scheduled_start, field="scheduled_start")
        observed = _parse_time(self.source_observed_at, field="source_observed_at")
        if observed >= scheduled:
            raise ValueError("web fixture must be observed before scheduled start")


@dataclass(frozen=True)
class WebShadowPrediction:
    fixture: WebShadowFixture
    committed_at: str
    p_player_a: float
    p_player_b: float
    model_source_sha: str
    input_manifest_sha256: str

    def record(self) -> dict[str, object]:
        self.fixture.validate()
        committed = _parse_time(self.committed_at, field="committed_at")
        scheduled = _parse_time(self.fixture.scheduled_start, field="scheduled_start")
        if committed >= scheduled:
            raise ValueError("prediction must be committed before scheduled start")
        if not (math.isfinite(self.p_player_a) and math.isfinite(self.p_player_b)):
            raise ValueError("probabilities must be finite")
        if not (0.0 < self.p_player_a < 1.0 and 0.0 < self.p_player_b < 1.0):
            raise ValueError("probabilities must be strictly inside (0,1)")
        if abs(self.p_player_a + self.p_player_b - 1.0) > 1e-9:
            raise ValueError("probabilities must sum to one")
        selected_player = (
            self.fixture.player_a
            if self.p_player_a >= self.p_player_b
            else self.fixture.player_b
        )
        payload: dict[str, object] = {
            "schema_version": WEB_SHADOW_SCHEMA,
            "record_type": "WEB_SHADOW_PREDICTION",
            "fixture": asdict(self.fixture),
            "committed_at": self.committed_at,
            "p_player_a": self.p_player_a,
            "p_player_b": self.p_player_b,
            "selected_player": selected_player,
            "model_source_sha": self.model_source_sha,
            "input_manifest_sha256": self.input_manifest_sha256,
            "production_eligible": False,
        }
        payload["record_sha256"] = _sha(payload)
        return payload


def settle_web_shadow(
    prediction: dict[str, object],
    *,
    winner: str,
    status: str,
    result_source_url: str,
    result_observed_at: str,
) -> dict[str, object]:
    if prediction.get("schema_version") != WEB_SHADOW_SCHEMA:
        raise ValueError("unsupported web-shadow prediction schema")
    if prediction.get("record_type") != "WEB_SHADOW_PREDICTION":
        raise ValueError("record is not a web-shadow prediction")
    unsigned = dict(prediction)
    observed_sha = str(unsigned.pop("record_sha256", ""))
    if _sha(unsigned) != observed_sha:
        raise ValueError("prediction record digest mismatch")
    fixture = prediction.get("fixture")
    if not isinstance(fixture, dict):
        raise ValueError("prediction fixture is missing")
    players = {str(fixture.get("player_a", "")), str(fixture.get("player_b", ""))}
    if winner not in players:
        raise ValueError("winner must be one of the frozen fixture players")
    normalized_status = status.upper()
    if normalized_status not in _ALLOWED_STATUSES - {"SCHEDULED"}:
        raise ValueError("settlement status is unsupported")
    if not result_source_url.strip():
        raise ValueError("result_source_url must be non-empty")
    observed = _parse_time(result_observed_at, field="result_observed_at")
    scheduled = _parse_time(str(fixture["scheduled_start"]), field="scheduled_start")
    if observed <= scheduled:
        raise ValueError("result observation must occur after scheduled start")
    payload: dict[str, object] = {
        "schema_version": WEB_SHADOW_SCHEMA,
        "record_type": "WEB_SHADOW_SETTLEMENT",
        "prediction_record_sha256": observed_sha,
        "match_id": fixture["match_id"],
        "winner": winner,
        "status": normalized_status,
        "result_source_url": result_source_url,
        "result_observed_at": result_observed_at,
        "prediction_correct": winner == prediction.get("selected_player"),
        "production_eligible": False,
    }
    payload["record_sha256"] = _sha(payload)
    return payload


def write_record(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
