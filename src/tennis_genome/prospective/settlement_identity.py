from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_github_anchor import GitHubGetBytes
from tennis_genome.prospective.trusted_capture_anchor import (
    fetch_authenticated_trusted_capture_evidence,
)

IDENTITY_SCHEMA = "full-stack-pilot-sportradar-identity-v1"
IDENTITY_VERSION = "FULL-STACK-PILOT-001-sportradar-identity-v1"
_PROVIDER = "SPORTRADAR_TENNIS_V3"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SettlementIdentityBinding:
    schema_version: str
    identity_version: str
    provider: str
    match_id: str
    tour: str
    sportradar_event_id: str
    player_a_canonical_id: str
    player_b_canonical_id: str
    player_a_sportradar_id: str
    player_b_sportradar_id: str
    player_a_sportradar_name: str
    player_b_sportradar_name: str
    scheduled_start: str
    provider_batch_record_sha256: str
    provider_batch_raw_sha256: str
    provider_anchor_comment_id: int
    provider_observed_at: str
    mapping_method: str
    artifact_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _self_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _sha256(_canonical_json(unsigned))


def _required_text(raw: dict[str, object], field: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} must be non-empty")
    return value


def _require_sha256(value: object, *, field: str) -> str:
    text = str(value if value is not None else "").strip()
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text


def _parse_time(value: object, *, field: str) -> datetime:
    text = str(value if value is not None else "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _as_dict(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _as_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _find_batch_record(
    batch_store: ProviderBatchStore,
    record_sha256: str,
) -> dict[str, object]:
    _require_sha256(record_sha256, field="provider_batch_record_sha256")
    matches = [
        record
        for record in batch_store.records()
        if str(record.get("record_sha256", "")) == record_sha256
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one provider batch record {record_sha256}")
    return matches[0]


def _provider_event(
    raw_payload: dict[str, object],
    *,
    sportradar_event_id: str,
) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for raw_summary in _as_list(raw_payload.get("summaries"), field="summaries"):
        summary = _as_dict(raw_summary, field="summary")
        event = _as_dict(summary.get("sport_event"), field="sport_event")
        if str(event.get("id", "")).strip() == sportradar_event_id:
            matches.append(summary)
    if len(matches) != 1:
        raise ValueError("trusted provider batch must contain target event exactly once")
    return matches[0]


def _competitors(event: dict[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for raw in _as_list(event.get("competitors"), field="sport_event.competitors"):
        competitor = _as_dict(raw, field="competitor")
        competitor_id = _required_text(competitor, "id")
        if competitor_id in result:
            raise ValueError("Sportradar event contains duplicate competitor ID")
        result[competitor_id] = competitor
    if len(result) != 2:
        raise ValueError("settlement identity requires exactly two Sportradar competitors")
    return result


def build_identity_binding(
    *,
    batch_store: ProviderBatchStore,
    batch_record_sha256: str,
    provider_anchor_comment_id: int,
    match_id: str,
    player_a_canonical_id: str,
    player_b_canonical_id: str,
    sportradar_event_id: str,
    player_a_sportradar_id: str,
    player_b_sportradar_id: str,
    github_get_bytes: GitHubGetBytes | None = None,
) -> SettlementIdentityBinding:
    """Seal provider/canonical A/B identity from authenticated pre-match evidence."""

    batch_store.verify()
    batch_record = _find_batch_record(batch_store, batch_record_sha256)
    fetch_authenticated_trusted_capture_evidence(
        comment_id=provider_anchor_comment_id,
        batch_record=batch_record,
        get_bytes=github_get_bytes,
    )

    match_id = match_id.strip()
    canonical_a = player_a_canonical_id.strip()
    canonical_b = player_b_canonical_id.strip()
    event_id = sportradar_event_id.strip()
    sr_a = player_a_sportradar_id.strip()
    sr_b = player_b_sportradar_id.strip()
    if not all((match_id, canonical_a, canonical_b, event_id, sr_a, sr_b)):
        raise ValueError("settlement identity fields must be non-empty")
    if canonical_a >= canonical_b:
        raise ValueError("canonical Player A/B must preserve ascending frozen orientation")
    if sr_a == sr_b:
        raise ValueError("Sportradar competitor IDs must be distinct")
    if provider_anchor_comment_id <= 0:
        raise ValueError("provider anchor comment ID must be positive")

    raw_sha = _require_sha256(
        batch_record.get("raw_payload_sha256"),
        field="provider_batch_raw_sha256",
    )
    raw_path = batch_store.evidence_dir / raw_sha
    if not raw_path.is_file():
        raise ValueError("trusted provider batch raw evidence is missing")
    raw_payload = _load_json_object(raw_path, label="trusted provider batch raw payload")
    summary = _provider_event(raw_payload, sportradar_event_id=event_id)
    event = _as_dict(summary.get("sport_event"), field="sport_event")
    context = _as_dict(event.get("sport_event_context"), field="sport_event_context")
    category = _as_dict(context.get("category"), field="sport_event_context.category")
    competition = _as_dict(
        context.get("competition"),
        field="sport_event_context.competition",
    )
    category_id = _required_text(category, "id")
    category_name = _required_text(category, "name").upper()
    if category_id == "sr:category:3" and category_name == "ATP":
        tour = "ATP"
    elif category_id == "sr:category:6" and category_name == "WTA":
        tour = "WTA"
    else:
        raise ValueError("settlement identity event is not ATP/WTA")
    if _required_text(competition, "type").lower() != "singles":
        raise ValueError("settlement identity event is not singles")

    scheduled_dt = _parse_time(event.get("start_time"), field="sport_event.start_time")
    observed_dt = _parse_time(batch_record.get("observed_at"), field="provider.observed_at")
    if observed_dt >= scheduled_dt:
        raise ValueError("settlement identity must be bound from a pre-match provider batch")

    competitors = _competitors(event)
    if set(competitors) != {sr_a, sr_b}:
        raise ValueError("requested A/B Sportradar IDs do not equal provider event competitors")
    competitor_a = competitors[sr_a]
    competitor_b = competitors[sr_b]
    if bool(competitor_a.get("virtual", False)) or bool(competitor_b.get("virtual", False)):
        raise ValueError("virtual/TBD competitors cannot be settlement identities")

    unsigned: dict[str, object] = {
        "schema_version": IDENTITY_SCHEMA,
        "identity_version": IDENTITY_VERSION,
        "provider": _PROVIDER,
        "match_id": match_id,
        "tour": tour,
        "sportradar_event_id": event_id,
        "player_a_canonical_id": canonical_a,
        "player_b_canonical_id": canonical_b,
        "player_a_sportradar_id": sr_a,
        "player_b_sportradar_id": sr_b,
        "player_a_sportradar_name": _required_text(competitor_a, "name"),
        "player_b_sportradar_name": _required_text(competitor_b, "name"),
        "scheduled_start": scheduled_dt.isoformat(),
        "provider_batch_record_sha256": batch_record_sha256,
        "provider_batch_raw_sha256": raw_sha,
        "provider_anchor_comment_id": provider_anchor_comment_id,
        "provider_observed_at": observed_dt.isoformat(),
        "mapping_method": "PREMATCH_PROVIDER_EVENT_EXPLICIT_A_B",
    }
    return SettlementIdentityBinding(
        **unsigned,
        artifact_sha256=_self_hash(unsigned),
    )


def identity_as_dict(binding: SettlementIdentityBinding) -> dict[str, object]:
    return asdict(binding)


def verify_identity_binding(payload: dict[str, object]) -> SettlementIdentityBinding:
    if payload.get("schema_version") != IDENTITY_SCHEMA:
        raise ValueError("unexpected settlement identity schema")
    if payload.get("identity_version") != IDENTITY_VERSION:
        raise ValueError("unexpected settlement identity version")
    if payload.get("provider") != _PROVIDER:
        raise ValueError("unexpected settlement identity provider")
    if str(payload.get("artifact_sha256", "")) != _self_hash(payload):
        raise ValueError("settlement identity digest mismatch")
    binding = SettlementIdentityBinding(**payload)
    if not binding.match_id.strip() or not binding.sportradar_event_id.strip():
        raise ValueError("settlement identity match/event IDs must be non-empty")
    if binding.tour not in {"ATP", "WTA"}:
        raise ValueError("settlement identity tour must be ATP or WTA")
    if binding.player_a_canonical_id >= binding.player_b_canonical_id:
        raise ValueError("settlement identity canonical A/B orientation is invalid")
    if binding.player_a_sportradar_id == binding.player_b_sportradar_id:
        raise ValueError("settlement identity Sportradar competitor IDs must differ")
    if binding.mapping_method != "PREMATCH_PROVIDER_EVENT_EXPLICIT_A_B":
        raise ValueError("settlement identity mapping method is not supported")
    if binding.provider_anchor_comment_id <= 0:
        raise ValueError("settlement identity provider anchor comment ID must be positive")
    _require_sha256(
        binding.provider_batch_record_sha256,
        field="provider_batch_record_sha256",
    )
    _require_sha256(binding.provider_batch_raw_sha256, field="provider_batch_raw_sha256")
    _parse_time(binding.scheduled_start, field="identity.scheduled_start")
    _parse_time(binding.provider_observed_at, field="identity.provider_observed_at")
    return binding


def authenticate_identity_binding(
    *,
    payload: dict[str, object],
    batch_store: ProviderBatchStore,
    github_get_bytes: GitHubGetBytes | None = None,
) -> SettlementIdentityBinding:
    """Rebuild a committed identity from trusted provider evidence and compare exactly."""

    binding = verify_identity_binding(payload)
    rebuilt = build_identity_binding(
        batch_store=batch_store,
        batch_record_sha256=binding.provider_batch_record_sha256,
        provider_anchor_comment_id=binding.provider_anchor_comment_id,
        match_id=binding.match_id,
        player_a_canonical_id=binding.player_a_canonical_id,
        player_b_canonical_id=binding.player_b_canonical_id,
        sportradar_event_id=binding.sportradar_event_id,
        player_a_sportradar_id=binding.player_a_sportradar_id,
        player_b_sportradar_id=binding.player_b_sportradar_id,
        github_get_bytes=github_get_bytes,
    )
    if _canonical_json(identity_as_dict(binding)) != _canonical_json(identity_as_dict(rebuilt)):
        raise ValueError("settlement identity does not reproduce from trusted provider evidence")
    return binding


def find_prediction_identity_binding(
    *,
    pilot_store: object,
    prediction: dict[str, object],
) -> tuple[SettlementIdentityBinding, str, dict[str, object]]:
    evidence_dir = Path(getattr(pilot_store, "evidence_dir"))
    prediction_start = _parse_time(
        prediction.get("scheduled_start"),
        field="prediction.scheduled_start",
    )
    candidates: list[tuple[SettlementIdentityBinding, str, dict[str, object]]] = []
    for raw_sha in prediction.get("source_manifest_hashes", []):
        digest = str(raw_sha)
        path = evidence_dir / digest
        if not path.is_file():
            continue
        try:
            payload = _load_json_object(path, label="prediction source evidence")
        except ValueError:
            continue
        if payload.get("schema_version") != IDENTITY_SCHEMA:
            continue
        binding = verify_identity_binding(payload)
        if binding.match_id != prediction.get("match_id"):
            continue
        if binding.tour != prediction.get("tour"):
            continue
        if binding.player_a_canonical_id != prediction.get("player_a_id"):
            continue
        if binding.player_b_canonical_id != prediction.get("player_b_id"):
            continue
        identity_start = _parse_time(
            binding.scheduled_start,
            field="identity.scheduled_start",
        )
        if identity_start != prediction_start:
            continue
        candidates.append((binding, digest, payload))
    if len(candidates) != 1:
        raise ValueError(
            "prediction must retain exactly one matching pre-match Sportradar identity binding"
        )
    return candidates[0]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seal pre-match Sportradar/canonical identity for pilot settlement"
    )
    parser.add_argument("--provider-batch-store", required=True, type=Path)
    parser.add_argument("--batch-record-sha256", required=True)
    parser.add_argument("--provider-anchor-comment-id", required=True, type=int)
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--player-a-canonical-id", required=True)
    parser.add_argument("--player-b-canonical-id", required=True)
    parser.add_argument("--sportradar-event-id", required=True)
    parser.add_argument("--player-a-sportradar-id", required=True)
    parser.add_argument("--player-b-sportradar-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    binding = build_identity_binding(
        batch_store=ProviderBatchStore(args.provider_batch_store),
        batch_record_sha256=args.batch_record_sha256,
        provider_anchor_comment_id=args.provider_anchor_comment_id,
        match_id=args.match_id,
        player_a_canonical_id=args.player_a_canonical_id,
        player_b_canonical_id=args.player_b_canonical_id,
        sportradar_event_id=args.sportradar_event_id,
        player_a_sportradar_id=args.player_a_sportradar_id,
        player_b_sportradar_id=args.player_b_sportradar_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(_pretty_json(identity_as_dict(binding)))
    print(_pretty_json(identity_as_dict(binding)).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
