from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from tennis_genome.experiments.pattern_confirm import (
    FrozenMarketCoreFit,
    ProspectiveRecord,
    SettledOutcome,
    build_prospective_record,
    evaluate_family,
    prospective_record_as_dict,
    report_as_dict,
    verify_fit_payload,
    verify_prospective_record,
)
from tennis_genome.experiments.pattern_confirm_live_identity import (
    IdentityMapping,
    parse_sportradar_actual_start,
    parse_sportradar_prematch_event,
    validate_mapping_against_event,
    verify_identity_mapping,
)
from tennis_genome.experiments.pattern_confirm_production import (
    CoreProductionArtifact,
    ProfileProductionArtifact,
    verify_core_artifact,
    verify_profile_artifact,
)

_EXPERIMENT_ID = "PATTERN-CONFIRM-001"
_VERSION = "pattern-confirm-live-v2"
_MARKET_PROVIDER = "THE_ODDS_API_V4_PINNACLE_V1"
_MARKET_SOURCE = "PINNACLE_H2H_V1"
_EVENT_PROVIDER = "SPORTRADAR_TENNIS_V3"
_REQUIRED_MATCH_STATE = "PREMATCH"
_MIN_START_LEAD = timedelta(minutes=5)
_MAX_SNAPSHOT_STALENESS = timedelta(minutes=5)


@dataclass(frozen=True)
class LiveProspectiveRecord:
    experiment_id: str
    version: str
    match_id: str
    tour: str
    scheduled_start: str
    market_provider: str
    market_source: str
    event_provider: str
    market_event_id: str
    sportradar_event_id: str
    player_a_market_name: str
    player_b_market_name: str
    player_a_sportradar_id: str
    player_b_sportradar_id: str
    player_a_id: str
    player_b_id: str
    identity_mapping_sha256: str
    sportradar_summary_sha256: str
    provider_match_state: str
    provider_snapshot_at: str
    ingested_at: str
    prediction_generated_at: str
    prediction_committed_at: str
    decimal_odds_a: float
    decimal_odds_b: float
    market_probability_a: float
    core_probability_a: float
    profile_gap: float
    profile_model_sha256: str
    core_model_sha256: str
    market_core_fit_sha256: str
    core_record: ProspectiveRecord
    source_row_sha256: str
    record_sha256: str


@dataclass(frozen=True)
class LiveSettlement:
    match_id: str
    sportradar_event_id: str
    actual_start: str | None
    actual_start_source: str
    actual_start_exclusion_reason: str | None
    timeline_sha256: str
    outcome_a: bool | None
    retirement: bool
    walkover: bool


@dataclass(frozen=True)
class TimingExclusion:
    match_id: str
    sportradar_event_id: str
    provider_snapshot_at: str
    prediction_committed_at: str
    actual_start: str | None
    reason: str


@dataclass(frozen=True)
class LiveConfirmationReport:
    experiment_id: str
    version: str
    market_provider: str
    market_source: str
    event_provider: str
    profile_model_sha256: str
    core_model_sha256: str
    market_core_fit_sha256: str
    live_ledger_sha256: str
    settlement_file_sha256: str
    timing_exclusions: tuple[TimingExclusion, ...]
    core_confirmation: dict[str, object]
    artifact_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _self_hash(payload: dict[str, object], field: str = "record_sha256") -> str:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return _sha256_bytes(_canonical_json(unsigned))


def _parse_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("live timestamps must be timezone-aware ISO-8601 values")
    return parsed


def _required_text(raw: dict[str, object], name: str) -> str:
    value = str(raw.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _required_sha(raw: dict[str, object], name: str) -> str:
    value = _required_text(raw, name).lower()
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _required_object(raw: dict[str, object], name: str) -> dict[str, object]:
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _required_bool(raw: dict[str, object], name: str) -> bool:
    value = raw.get(name)
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a JSON boolean")
    return value


def _optional_bool(raw: dict[str, object], name: str) -> bool | None:
    value = raw.get(name)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a JSON boolean or null")
    return value


def _decimal_odds(raw: dict[str, object], name: str) -> float:
    value = float(raw.get(name))
    if not math.isfinite(value) or value <= 1.0:
        raise ValueError(f"{name} must be finite decimal odds greater than 1")
    return value


def _devig_probability(odds_a: float, odds_b: float) -> float:
    q_a = 1.0 / odds_a
    q_b = 1.0 / odds_b
    return q_a / (q_a + q_b)


def live_record_as_dict(record: LiveProspectiveRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["core_record"] = prospective_record_as_dict(record.core_record)
    return payload


def verify_live_record(
    payload: dict[str, object],
    *,
    fit: FrozenMarketCoreFit,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
    identity_mapping: IdentityMapping,
) -> LiveProspectiveRecord:
    stored = str(payload.get("record_sha256", ""))
    unsigned = dict(payload)
    unsigned.pop("record_sha256", None)
    if not stored or _sha256_bytes(_canonical_json(unsigned)) != stored:
        raise ValueError("live prospective record digest mismatch")
    core_payload = payload.get("core_record")
    if not isinstance(core_payload, dict):
        raise ValueError("live record is missing its sealed core record")
    core_record = verify_prospective_record(core_payload)
    normalized = dict(payload)
    normalized["core_record"] = core_record
    record = LiveProspectiveRecord(**normalized)
    if record.experiment_id != _EXPERIMENT_ID or record.version != _VERSION:
        raise ValueError("unexpected live prospective record contract")
    if record.market_provider != _MARKET_PROVIDER or record.market_source != _MARKET_SOURCE:
        raise ValueError("sealed live row violates frozen Pinnacle market contract")
    if record.event_provider != _EVENT_PROVIDER:
        raise ValueError("sealed live row violates frozen event-provider contract")
    if record.provider_match_state != _REQUIRED_MATCH_STATE:
        raise ValueError("sealed live row was not captured PREMATCH")
    if record.profile_model_sha256 != profile_artifact.artifact_sha256:
        raise ValueError("live ledger mixes Profile production artifact versions")
    if record.core_model_sha256 != core_artifact.artifact_sha256:
        raise ValueError("live ledger mixes Core production artifact versions")
    if record.market_core_fit_sha256 != fit.artifact_sha256:
        raise ValueError("live ledger mixes Market+Core fit versions")
    if record.identity_mapping_sha256 != identity_mapping.artifact_sha256:
        raise ValueError("live ledger identity mapping hash mismatch")
    if record.market_event_id != identity_mapping.market_event_id:
        raise ValueError("live ledger market event does not match identity mapping")
    if record.sportradar_event_id != identity_mapping.sportradar_event_id:
        raise ValueError("live ledger Sportradar event does not match identity mapping")
    if record.player_a_market_name != identity_mapping.player_a_market_name:
        raise ValueError("live ledger market player A does not match identity mapping")
    if record.player_b_market_name != identity_mapping.player_b_market_name:
        raise ValueError("live ledger market player B does not match identity mapping")
    if record.player_a_sportradar_id != identity_mapping.player_a_sportradar_id:
        raise ValueError("live ledger Sportradar player A does not match identity mapping")
    if record.player_b_sportradar_id != identity_mapping.player_b_sportradar_id:
        raise ValueError("live ledger Sportradar player B does not match identity mapping")
    if record.player_a_id != identity_mapping.player_a_canonical_id:
        raise ValueError("live ledger player A does not match identity mapping")
    if record.player_b_id != identity_mapping.player_b_canonical_id:
        raise ValueError("live ledger player B does not match identity mapping")
    if record.scheduled_start != identity_mapping.scheduled_start:
        raise ValueError("live ledger scheduled start does not match identity mapping")

    scheduled = _parse_time(record.scheduled_start)
    snapshot = _parse_time(record.provider_snapshot_at)
    ingested = _parse_time(record.ingested_at)
    generated = _parse_time(record.prediction_generated_at)
    committed = _parse_time(record.prediction_committed_at)
    if snapshot > ingested:
        raise ValueError("sealed provider snapshot is later than ingestion")
    if ingested - snapshot > _MAX_SNAPSHOT_STALENESS:
        raise ValueError("sealed provider snapshot is stale at ingestion")
    if ingested > generated or generated > committed:
        raise ValueError("sealed live row timestamps are out of order")
    if snapshot > scheduled - _MIN_START_LEAD:
        raise ValueError("sealed market snapshot violates scheduled T-minus-five gate")
    if committed >= scheduled:
        raise ValueError("sealed prediction was not committed before scheduled start")
    if (
        not math.isfinite(record.decimal_odds_a)
        or not math.isfinite(record.decimal_odds_b)
        or record.decimal_odds_a <= 1.0
        or record.decimal_odds_b <= 1.0
    ):
        raise ValueError("sealed decimal odds are invalid")
    expected_market = _devig_probability(record.decimal_odds_a, record.decimal_odds_b)
    if record.market_probability_a != expected_market:
        raise ValueError("sealed market probability does not reproduce from raw odds")
    if not math.isfinite(record.core_probability_a) or not 0.0 < record.core_probability_a < 1.0:
        raise ValueError("sealed Core probability is invalid")
    if not math.isfinite(record.profile_gap):
        raise ValueError("sealed Profile Gap is invalid")
    if core_record.match_id != record.match_id or core_record.tour != record.tour:
        raise ValueError("sealed core record identity does not match live envelope")
    if core_record.scheduled_start != record.scheduled_start:
        raise ValueError("sealed core record start time does not match live envelope")
    if core_record.market_probability_a != record.market_probability_a:
        raise ValueError("sealed core market probability does not match live envelope")
    if core_record.core_probability_a != record.core_probability_a:
        raise ValueError("sealed core probability does not match live envelope")
    if core_record.profile_gap != record.profile_gap:
        raise ValueError("sealed core Profile Gap does not match live envelope")
    if core_record.market_core_fit_sha256 != fit.artifact_sha256:
        raise ValueError("sealed core Market+Core fit does not match live envelope")
    return record


def build_live_record(
    raw: dict[str, object],
    *,
    fit: FrozenMarketCoreFit,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
    identity_mapping: IdentityMapping,
) -> LiveProspectiveRecord:
    match_id = _required_text(raw, "match_id")
    tour = _required_text(raw, "tour")
    if tour != "ATP":
        raise ValueError("PATTERN-CONFIRM-001 live intake is ATP only")

    market_provider = _required_text(raw, "market_provider")
    market_source = _required_text(raw, "market_source")
    if market_provider != _MARKET_PROVIDER or market_source != _MARKET_SOURCE:
        raise ValueError("live market source does not match frozen Pinnacle contract")
    if _required_text(raw, "provider_match_state") != _REQUIRED_MATCH_STATE:
        raise ValueError("market snapshot must be explicitly PREMATCH")

    market_event_id = _required_text(raw, "market_event_id")
    player_a_market_name = _required_text(raw, "player_a_market_name")
    player_b_market_name = _required_text(raw, "player_b_market_name")
    if market_event_id != identity_mapping.market_event_id:
        raise ValueError("market event does not match verified identity mapping")
    if player_a_market_name != identity_mapping.player_a_market_name:
        raise ValueError("market player A orientation does not match identity mapping")
    if player_b_market_name != identity_mapping.player_b_market_name:
        raise ValueError("market player B orientation does not match identity mapping")

    summary_payload = _required_object(raw, "sportradar_summary")
    event = parse_sportradar_prematch_event(
        summary_payload,
        expected_event_id=identity_mapping.sportradar_event_id,
    )
    validate_mapping_against_event(identity_mapping, event)

    supplied_profile_sha = _required_sha(raw, "profile_model_sha256")
    supplied_core_sha = _required_sha(raw, "core_model_sha256")
    if supplied_profile_sha != profile_artifact.artifact_sha256:
        raise ValueError("profile_model_sha256 does not match frozen Profile artifact")
    if supplied_core_sha != core_artifact.artifact_sha256:
        raise ValueError("core_model_sha256 does not match frozen Core artifact")

    scheduled_start = _parse_time(identity_mapping.scheduled_start)
    provider_snapshot = _parse_time(raw.get("provider_snapshot_at"))
    ingested = _parse_time(raw.get("ingested_at"))
    generated = _parse_time(raw.get("prediction_generated_at"))
    committed = _parse_time(raw.get("prediction_committed_at"))
    if provider_snapshot > ingested:
        raise ValueError("provider snapshot cannot be later than ingestion")
    if ingested - provider_snapshot > _MAX_SNAPSHOT_STALENESS:
        raise ValueError("provider snapshot is stale at ingestion")
    if ingested > generated or generated > committed:
        raise ValueError("ingestion/generation/commit timestamps are out of order")
    if provider_snapshot > scheduled_start - _MIN_START_LEAD:
        raise ValueError("market snapshot is less than five minutes before scheduled start")
    if committed >= scheduled_start:
        raise ValueError("prediction must be committed before scheduled start")

    odds_a = _decimal_odds(raw, "decimal_odds_a")
    odds_b = _decimal_odds(raw, "decimal_odds_b")
    market_probability = _devig_probability(odds_a, odds_b)
    core_probability = float(raw.get("core_probability_a"))
    profile_gap = float(raw.get("profile_gap"))
    if not math.isfinite(core_probability) or not 0.0 < core_probability < 1.0:
        raise ValueError("core_probability_a must be finite and in (0, 1)")
    if not math.isfinite(profile_gap):
        raise ValueError("profile_gap must be finite")

    core_record = build_prospective_record(
        {
            "match_id": match_id,
            "tour": tour,
            "scheduled_start": scheduled_start.isoformat(),
            "observed_at": provider_snapshot.isoformat(),
            "market_source": f"{market_provider}/{market_source}",
            "market_probability_a": market_probability,
            "core_probability_a": core_probability,
            "profile_gap": profile_gap,
        },
        fit=fit,
    )
    source_sha = _sha256_bytes(_canonical_json(raw))
    summary_sha = _sha256_bytes(_canonical_json(summary_payload))
    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "match_id": match_id,
        "tour": tour,
        "scheduled_start": scheduled_start.isoformat(),
        "market_provider": market_provider,
        "market_source": market_source,
        "event_provider": _EVENT_PROVIDER,
        "market_event_id": market_event_id,
        "sportradar_event_id": identity_mapping.sportradar_event_id,
        "player_a_market_name": player_a_market_name,
        "player_b_market_name": player_b_market_name,
        "player_a_sportradar_id": identity_mapping.player_a_sportradar_id,
        "player_b_sportradar_id": identity_mapping.player_b_sportradar_id,
        "player_a_id": identity_mapping.player_a_canonical_id,
        "player_b_id": identity_mapping.player_b_canonical_id,
        "identity_mapping_sha256": identity_mapping.artifact_sha256,
        "sportradar_summary_sha256": summary_sha,
        "provider_match_state": _REQUIRED_MATCH_STATE,
        "provider_snapshot_at": provider_snapshot.isoformat(),
        "ingested_at": ingested.isoformat(),
        "prediction_generated_at": generated.isoformat(),
        "prediction_committed_at": committed.isoformat(),
        "decimal_odds_a": odds_a,
        "decimal_odds_b": odds_b,
        "market_probability_a": market_probability,
        "core_probability_a": core_probability,
        "profile_gap": profile_gap,
        "profile_model_sha256": profile_artifact.artifact_sha256,
        "core_model_sha256": core_artifact.artifact_sha256,
        "market_core_fit_sha256": fit.artifact_sha256,
        "core_record": prospective_record_as_dict(core_record),
        "source_row_sha256": source_sha,
    }
    digest = _sha256_bytes(_canonical_json(unsigned))
    return LiveProspectiveRecord(
        **{**unsigned, "core_record": core_record},
        record_sha256=digest,
    )


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("JSONL rows must be objects")
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows)
    )


def load_identity_mappings(rows: list[dict[str, object]]) -> dict[str, IdentityMapping]:
    result: dict[str, IdentityMapping] = {}
    for raw in rows:
        mapping = verify_identity_mapping(raw)
        if mapping.market_event_id in result:
            raise ValueError("identity mapping file contains duplicate market_event_id")
        result[mapping.market_event_id] = mapping
    return result


def append_live_rows(
    *,
    existing_rows: list[dict[str, object]],
    new_rows: list[dict[str, object]],
    identity_mappings: dict[str, IdentityMapping],
    fit: FrozenMarketCoreFit,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
) -> list[LiveProspectiveRecord]:
    existing: list[LiveProspectiveRecord] = []
    for row in existing_rows:
        market_event_id = _required_text(row, "market_event_id")
        mapping = identity_mappings.get(market_event_id)
        if mapping is None:
            raise ValueError("existing live row has no verified identity mapping")
        existing.append(
            verify_live_record(
                row,
                fit=fit,
                profile_artifact=profile_artifact,
                core_artifact=core_artifact,
                identity_mapping=mapping,
            )
        )

    additions: list[LiveProspectiveRecord] = []
    for row in new_rows:
        market_event_id = _required_text(row, "market_event_id")
        mapping = identity_mappings.get(market_event_id)
        if mapping is None:
            raise ValueError("new live row has no verified identity mapping")
        additions.append(
            build_live_record(
                row,
                fit=fit,
                profile_artifact=profile_artifact,
                core_artifact=core_artifact,
                identity_mapping=mapping,
            )
        )

    ids = [record.match_id for record in [*existing, *additions]]
    if len(ids) != len(set(ids)):
        raise ValueError("live prospective ledger contains duplicate match_id values")
    return sorted(
        [*existing, *additions],
        key=lambda record: (_parse_time(record.scheduled_start), record.match_id),
    )


def load_live_settlements(rows: list[dict[str, object]]) -> dict[str, LiveSettlement]:
    result: dict[str, LiveSettlement] = {}
    for raw in rows:
        match_id = _required_text(raw, "match_id")
        if match_id in result:
            raise ValueError("settlements require unique match_id values")
        sportradar_event_id = _required_text(raw, "sportradar_event_id")
        timeline_payload = _required_object(raw, "sportradar_timeline")
        timing = parse_sportradar_actual_start(
            timeline_payload,
            expected_event_id=sportradar_event_id,
        )
        retirement = _required_bool(raw, "retirement")
        walkover = _required_bool(raw, "walkover")
        outcome = _optional_bool(raw, "outcome_a")
        if not retirement and not walkover and outcome is None:
            raise ValueError("settled non-excluded rows require outcome_a")
        result[match_id] = LiveSettlement(
            match_id=match_id,
            sportradar_event_id=sportradar_event_id,
            actual_start=timing.actual_start,
            actual_start_source=timing.source,
            actual_start_exclusion_reason=timing.exclusion_reason,
            timeline_sha256=timing.timeline_sha256,
            outcome_a=outcome,
            retirement=retirement,
            walkover=walkover,
        )
    return result


def _timing_check(
    record: LiveProspectiveRecord,
    settlement: LiveSettlement,
) -> str | None:
    if settlement.sportradar_event_id != record.sportradar_event_id:
        raise ValueError("settlement Sportradar event ID does not match prospective record")
    if settlement.actual_start is None:
        return settlement.actual_start_exclusion_reason or "ACTUAL_START_UNVERIFIED"
    actual_start = _parse_time(settlement.actual_start)
    snapshot = _parse_time(record.provider_snapshot_at)
    committed = _parse_time(record.prediction_committed_at)
    if snapshot > actual_start - _MIN_START_LEAD:
        return "PROVIDER_SNAPSHOT_NOT_T_MINUS_5"
    if committed >= actual_start:
        return "PREDICTION_NOT_COMMITTED_PRE_START"
    return None


def evaluate_live_family(
    records: list[LiveProspectiveRecord],
    settlements: dict[str, LiveSettlement],
    *,
    fit: FrozenMarketCoreFit,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
    ledger_sha256: str,
    settlement_sha256: str,
) -> LiveConfirmationReport:
    eligible_records: list[ProspectiveRecord] = []
    eligible_outcomes: dict[str, SettledOutcome] = {}
    timing_exclusions: list[TimingExclusion] = []
    for record in records:
        if record.profile_model_sha256 != profile_artifact.artifact_sha256:
            raise ValueError("Profile artifact version changed inside live evaluation")
        if record.core_model_sha256 != core_artifact.artifact_sha256:
            raise ValueError("Core artifact version changed inside live evaluation")
        settlement = settlements.get(record.match_id)
        if settlement is None:
            continue
        reason = _timing_check(record, settlement)
        if reason is not None:
            timing_exclusions.append(
                TimingExclusion(
                    match_id=record.match_id,
                    sportradar_event_id=record.sportradar_event_id,
                    provider_snapshot_at=record.provider_snapshot_at,
                    prediction_committed_at=record.prediction_committed_at,
                    actual_start=settlement.actual_start,
                    reason=reason,
                )
            )
            continue
        eligible_records.append(record.core_record)
        eligible_outcomes[record.match_id] = SettledOutcome(
            match_id=record.match_id,
            outcome_a=settlement.outcome_a,
            retirement=settlement.retirement,
            walkover=settlement.walkover,
        )

    core_report = evaluate_family(
        eligible_records,
        eligible_outcomes,
        fit=fit,
        ledger_sha256=ledger_sha256,
        outcomes_sha256=settlement_sha256,
    )
    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "market_provider": _MARKET_PROVIDER,
        "market_source": _MARKET_SOURCE,
        "event_provider": _EVENT_PROVIDER,
        "profile_model_sha256": profile_artifact.artifact_sha256,
        "core_model_sha256": core_artifact.artifact_sha256,
        "market_core_fit_sha256": fit.artifact_sha256,
        "live_ledger_sha256": ledger_sha256,
        "settlement_file_sha256": settlement_sha256,
        "timing_exclusions": [asdict(item) for item in timing_exclusions],
        "core_confirmation": report_as_dict(core_report),
    }
    digest = _self_hash(unsigned, field="artifact_sha256")
    return LiveConfirmationReport(
        experiment_id=_EXPERIMENT_ID,
        version=_VERSION,
        market_provider=_MARKET_PROVIDER,
        market_source=_MARKET_SOURCE,
        event_provider=_EVENT_PROVIDER,
        profile_model_sha256=profile_artifact.artifact_sha256,
        core_model_sha256=core_artifact.artifact_sha256,
        market_core_fit_sha256=fit.artifact_sha256,
        live_ledger_sha256=ledger_sha256,
        settlement_file_sha256=settlement_sha256,
        timing_exclusions=tuple(timing_exclusions),
        core_confirmation=report_as_dict(core_report),
        artifact_sha256=digest,
    )


def _load_contracts(
    fit_path: Path,
    profile_path: Path,
    core_path: Path,
) -> tuple[FrozenMarketCoreFit, ProfileProductionArtifact, CoreProductionArtifact]:
    fit = verify_fit_payload(json.loads(fit_path.read_text()))
    profile = verify_profile_artifact(json.loads(profile_path.read_text()))
    core = verify_core_artifact(json.loads(core_path.read_text()))
    return fit, profile, core


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PATTERN-CONFIRM-001 live intake firewall")
    parser.add_argument("--fit", required=True, type=Path)
    parser.add_argument("--profile-artifact", required=True, type=Path)
    parser.add_argument("--core-artifact", required=True, type=Path)
    parser.add_argument("--identity-mappings", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    append = sub.add_parser("append")
    append.add_argument("--existing", required=True, type=Path)
    append.add_argument("--input", required=True, type=Path)
    append.add_argument("--output", required=True, type=Path)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--ledger", required=True, type=Path)
    evaluate.add_argument("--settlements", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    fit, profile, core = _load_contracts(args.fit, args.profile_artifact, args.core_artifact)
    mappings = load_identity_mappings(_load_jsonl(args.identity_mappings))
    if args.command == "append":
        records = append_live_rows(
            existing_rows=_load_jsonl(args.existing),
            new_rows=_load_jsonl(args.input),
            identity_mappings=mappings,
            fit=fit,
            profile_artifact=profile,
            core_artifact=core,
        )
        _write_jsonl(args.output, [live_record_as_dict(record) for record in records])
        return
    if args.command == "evaluate":
        records: list[LiveProspectiveRecord] = []
        for row in _load_jsonl(args.ledger):
            market_event_id = _required_text(row, "market_event_id")
            mapping = mappings.get(market_event_id)
            if mapping is None:
                raise ValueError("live ledger row has no verified identity mapping")
            records.append(
                verify_live_record(
                    row,
                    fit=fit,
                    profile_artifact=profile,
                    core_artifact=core,
                    identity_mapping=mapping,
                )
            )
        settlements = load_live_settlements(_load_jsonl(args.settlements))
        report = evaluate_live_family(
            records,
            settlements,
            fit=fit,
            profile_artifact=profile,
            core_artifact=core,
            ledger_sha256=_sha256_file(args.ledger),
            settlement_sha256=_sha256_file(args.settlements),
        )
        args.output.write_text(
            json.dumps(asdict(report), indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
        return
    raise RuntimeError("unreachable command")


if __name__ == "__main__":
    main()
