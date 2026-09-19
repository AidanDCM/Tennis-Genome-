from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from tennis_genome.prospective.match_lifecycle import MatchLifecycleLedger
from tennis_genome.prospective.pilot import ProspectivePilotStore

CUTOVER_VALIDATION_VERSION = "tennis-genome-full-slate-cutover-validation-v1"
_ALLOWED_SKIP_REASONS = frozenset(
    {"TARGET_STATUS_NOT_PREMATCH", "SCHEDULED_START_REACHED"}
)


@dataclass(frozen=True)
class FullSlateCutoverAssessment:
    schema_version: str
    status: Literal["PASS"]
    eligible_target_count: int
    predicted_target_count: int
    skipped_target_count: int
    provider_unique_request_count: int
    provider_cached_path_count: int
    lifecycle_event_count: int
    lifecycle_chain_head_sha256: str
    prediction_record_sha256: tuple[str, ...]
    skipped_event_ids: tuple[str, ...]
    workflow_source_sha: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _require_sha256(value: object, *, label: str) -> str:
    text = str(value)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError(f"{label} must be lowercase SHA-256")
    return text


def assess_full_slate_cutover(
    root: Path,
    *,
    expected_source_sha: str,
) -> FullSlateCutoverAssessment:
    root = Path(root)
    _require_sha256(expected_source_sha, label="expected_source_sha")

    run_mode = _object(root / "forward-004-full-slate-run-mode.json")
    if run_mode.get("schema_version") != "wta-forward-004-full-slate-run-mode-v1":
        raise ValueError("unexpected full-slate run-mode schema")
    if run_mode.get("publish_prospective_evidence") is not False:
        raise ValueError("cutover validation requires a nonpublishing dry run")
    workflow_source_sha = _require_sha256(
        run_mode.get("workflow_source_sha"),
        label="workflow_source_sha",
    )
    if workflow_source_sha != expected_source_sha:
        raise ValueError("dry-run workflow source SHA differs from cutover candidate SHA")

    work = root / "forward-004-slate-work"
    resolution = _object(work / "forward-004-slate-resolution.json")
    execution = _object(work / "execution" / "slate-execution-manifest.json")
    if resolution.get("schema_version") != "wta-forward-004-slate-resolution-v1":
        raise ValueError("unexpected full-slate resolution schema")
    if execution.get("schema_version") != "wta-forward-004-slate-execution-v1":
        raise ValueError("unexpected full-slate execution schema")

    targets = resolution.get("targets")
    results = execution.get("results")
    skipped = execution.get("skipped_targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("dry-run slate has no eligible targets")
    if not isinstance(results, list) or not results:
        raise ValueError("dry-run slate has no Champion predictions")
    if not isinstance(skipped, list):
        raise ValueError("dry-run skipped_targets must be a list")

    eligible_n = int(resolution.get("eligible_target_count", -1))
    predicted_n = int(execution.get("target_count", -1))
    skipped_n = int(execution.get("skipped_target_count", -1))
    if eligible_n != len(targets):
        raise ValueError("resolution eligible target count does not reproduce")
    if int(execution.get("eligible_target_count", -2)) != eligible_n:
        raise ValueError("execution eligible target count differs from resolution")
    if predicted_n != len(results):
        raise ValueError("execution predicted target count does not reproduce")
    if skipped_n != len(skipped):
        raise ValueError("execution skipped target count does not reproduce")
    if predicted_n + skipped_n != eligible_n:
        raise ValueError("predicted + skipped does not equal eligible slate")

    target_ids = [str(item.get("event_id", "")) for item in targets if isinstance(item, dict)]
    result_ids = [str(item.get("event_id", "")) for item in results if isinstance(item, dict)]
    skipped_ids = [str(item.get("event_id", "")) for item in skipped if isinstance(item, dict)]
    if len(target_ids) != eligible_n or len(set(target_ids)) != eligible_n:
        raise ValueError("eligible target identities are incomplete or duplicated")
    if len(result_ids) != predicted_n or len(set(result_ids)) != predicted_n:
        raise ValueError("predicted target identities are incomplete or duplicated")
    if len(skipped_ids) != skipped_n or len(set(skipped_ids)) != skipped_n:
        raise ValueError("skipped target identities are incomplete or duplicated")
    if set(result_ids) & set(skipped_ids):
        raise ValueError("target cannot be both predicted and skipped")
    if set(result_ids) | set(skipped_ids) != set(target_ids):
        raise ValueError("predicted/skipped identities do not partition eligible slate")
    if [event_id for event_id in target_ids if event_id in set(result_ids)] != result_ids:
        raise ValueError("predicted target order does not preserve slate order")
    if [event_id for event_id in target_ids if event_id in set(skipped_ids)] != skipped_ids:
        raise ValueError("skipped target order does not preserve slate order")

    for item in skipped:
        assert isinstance(item, dict)
        if str(item.get("skip_reason", "")) not in _ALLOWED_SKIP_REASONS:
            raise ValueError("unrecognized full-slate skip reason")

    provider_unique = int(execution.get("provider_unique_request_count", -1))
    provider_cached = int(execution.get("provider_cached_path_count", -1))
    if provider_unique < 0 or provider_cached != provider_unique:
        raise ValueError("provider cache accounting does not reproduce")

    lifecycle = MatchLifecycleLedger(work / "execution" / "match-lifecycle-ledger")
    lifecycle_audit = lifecycle.verify()
    if lifecycle_audit.status != "PASS":
        raise ValueError("match lifecycle ledger did not verify")
    if lifecycle_audit.lifecycle_count != predicted_n:
        raise ValueError("match lifecycle count differs from predicted target count")
    if set(lifecycle_audit.lifecycle_states.values()) != {"CHAMPION_PREDICTED"}:
        raise ValueError("dry-run lifecycle advanced beyond Champion prediction")
    if lifecycle_audit.event_count != int(execution.get("lifecycle_event_count", -1)):
        raise ValueError("lifecycle event count differs from execution manifest")
    if lifecycle_audit.chain_head_sha256 != str(
        execution.get("lifecycle_chain_head_sha256", "")
    ):
        raise ValueError("lifecycle chain head differs from execution manifest")

    prediction_shas: list[str] = []
    result_by_id = {
        str(item["event_id"]): item
        for item in results
        if isinstance(item, dict) and "event_id" in item
    }
    for event_id in result_ids:
        item = result_by_id[event_id]
        artifact_stem = str(item.get("artifact_stem", ""))
        if not artifact_stem:
            raise ValueError("predicted target lacks artifact_stem")
        match_root = work / "execution" / "matches" / artifact_stem
        target = _object(match_root / "forward-004-target-resolution.json")
        if str(target.get("event_id", "")) != event_id:
            raise ValueError("per-match target resolution identity mismatch")

        prediction_root = match_root / "prediction-work"
        dossier = _object(prediction_root / "prediction-dossier.json")
        matchup = _object(prediction_root / "matchup-input.json")
        calculation = _object(prediction_root / "calculation.json")
        if str((dossier.get("target") or {}).get("event_id", "")) != event_id:
            raise ValueError("prediction dossier target identity mismatch")
        if str(matchup.get("match_id", "")) != event_id:
            raise ValueError("matchup input match identity mismatch")

        p_a = float((calculation.get("prediction") or {}).get("p_player_a"))
        p_b = float((calculation.get("prediction") or {}).get("p_player_b"))
        if not (math.isfinite(p_a) and math.isfinite(p_b)):
            raise ValueError("prediction probabilities must be finite")
        if not (0.0 < p_a < 1.0 and 0.0 < p_b < 1.0):
            raise ValueError("prediction probabilities must be strictly between zero and one")
        if abs((p_a + p_b) - 1.0) > 1e-9:
            raise ValueError("prediction probabilities do not sum to one")

        store = ProspectivePilotStore(prediction_root / "prospective-pilot-store")
        pilot = store.verify()
        if pilot.get("status") != "VERIFIED" or int(pilot.get("prediction_count", 0)) != 1:
            raise ValueError("per-match prospective pilot store did not verify")
        expected_prediction_sha = _require_sha256(
            item.get("prediction_record_sha256"),
            label="prediction_record_sha256",
        )
        if str(pilot.get("chain_head_sha256", "")) != expected_prediction_sha:
            raise ValueError("prediction SHA differs from verified pilot chain head")
        if str(item.get("chain_head_sha256", "")) != expected_prediction_sha:
            raise ValueError("execution chain head differs from prediction SHA")
        prediction_shas.append(expected_prediction_sha)

    if len(set(prediction_shas)) != predicted_n:
        raise ValueError("prediction record SHA values are not unique across slate")

    return FullSlateCutoverAssessment(
        schema_version=CUTOVER_VALIDATION_VERSION,
        status="PASS",
        eligible_target_count=eligible_n,
        predicted_target_count=predicted_n,
        skipped_target_count=skipped_n,
        provider_unique_request_count=provider_unique,
        provider_cached_path_count=provider_cached,
        lifecycle_event_count=lifecycle_audit.event_count,
        lifecycle_chain_head_sha256=lifecycle_audit.chain_head_sha256,
        prediction_record_sha256=tuple(prediction_shas),
        skipped_event_ids=tuple(skipped_ids),
        workflow_source_sha=workflow_source_sha,
    )
