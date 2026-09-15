from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tennis_genome.prospective.pilot import ProspectivePilotStore, settle_prediction
from tennis_genome.prospective.prediction_anchor_live import LivePredictionAnchorStore
from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_github_anchor import GitHubGetBytes
from tennis_genome.prospective.settlement_capture_github import (
    LiveSettlementCaptureEvidence,
    fetch_authenticated_settlement_capture_evidence,
    validate_retained_settlement_capture_evidence,
)
from tennis_genome.prospective.settlement_identity import (
    SettlementIdentityBinding,
    authenticate_identity_binding,
    find_prediction_identity_binding,
)

TRUSTED_SETTLEMENT_VERSION = "FULL-STACK-PILOT-001-trusted-settlement-store-v1"
TRUSTED_SETTLEMENT_MODE = "TRUSTED_GITHUB_SPORTRADAR_SETTLEMENT_V1"
_LEGACY_SETTLEMENT_SCHEMA = "full-stack-pilot-sportradar-settlement-v1"
_ZERO_SHA256 = "0" * 64


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


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(value: object, *, field: str) -> str:
    text = str(value if value is not None else "").strip()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text


def _record_sha256(unsigned: dict[str, object]) -> str:
    return _sha256_bytes(_canonical_json(unsigned))


def _strict_json_object(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    _fsync_directory(path.parent)


def _prediction_record(
    pilot_store: ProspectivePilotStore,
    prediction_sha256: str,
) -> dict[str, object]:
    prediction = pilot_store.find_record(prediction_sha256)
    if prediction.get("record_type") != "PREDICTION_COMMIT":
        raise ValueError("trusted settlement must reference a prediction commit")
    return prediction


def _pilot_settlement(
    pilot_store: ProspectivePilotStore,
    prediction_sha256: str,
) -> dict[str, object] | None:
    matches = [
        record
        for record in pilot_store.records()
        if record.get("record_type") == "SETTLEMENT"
        and record.get("prediction_record_sha256") == prediction_sha256
    ]
    if len(matches) > 1:
        raise ValueError("prediction has more than one pilot settlement")
    return None if not matches else matches[0]


def _timeline_contract(
    timeline_bytes: bytes,
    *,
    binding: SettlementIdentityBinding,
    evidence: LiveSettlementCaptureEvidence,
) -> dict[str, object]:
    timeline = _strict_json_object(timeline_bytes, label="trusted Sportradar timeline")
    event = timeline.get("sport_event")
    if not isinstance(event, dict) or event.get("id") != binding.sportradar_event_id:
        raise ValueError("trusted settlement timeline event differs from pre-match binding")
    status = timeline.get("sport_event_status")
    if not isinstance(status, dict):
        raise ValueError("trusted settlement timeline lacks sport_event_status")
    provider_status = str(status.get("status", "")).strip().lower()
    if provider_status not in {"ended", "closed"}:
        raise ValueError("trusted settlement timeline is not terminal")
    if provider_status != evidence.receipt.get("provider_status"):
        raise ValueError("trusted settlement provider status differs from receipt")
    winner = str(status.get("winner_id", "")).strip()
    if winner not in {
        binding.player_a_sportradar_id,
        binding.player_b_sportradar_id,
    }:
        raise ValueError("trusted settlement winner is not a pre-match competitor")
    if winner != evidence.receipt.get("winner_sportradar_id"):
        raise ValueError("trusted settlement winner differs from workflow receipt")
    generated = str(timeline.get("generated_at", "")).strip()
    if generated.endswith("Z"):
        generated = f"{generated[:-1]}+00:00"
    from datetime import datetime, UTC

    try:
        generated_at = datetime.fromisoformat(generated)
    except ValueError as exc:
        raise ValueError("trusted settlement timeline generated_at is invalid") from exc
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("trusted settlement timeline generated_at must be timezone-aware")
    if generated_at.astimezone(UTC) != evidence.provider_generated_at:
        raise ValueError("trusted settlement generated_at differs from workflow receipt")
    return timeline


def _legacy_wrapper(
    *,
    prediction: dict[str, object],
    binding: SettlementIdentityBinding,
    evidence: LiveSettlementCaptureEvidence,
    timeline: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": _LEGACY_SETTLEMENT_SCHEMA,
        "match_id": prediction["match_id"],
        "player_a_canonical_id": prediction["player_a_id"],
        "player_b_canonical_id": prediction["player_b_id"],
        "player_a_sportradar_id": binding.player_a_sportradar_id,
        "player_b_sportradar_id": binding.player_b_sportradar_id,
        "sportradar_event_id": binding.sportradar_event_id,
        "observed_at": evidence.observed_at.isoformat(),
        "sportradar_timeline": timeline,
    }


def _same_commitment(
    retained: LiveSettlementCaptureEvidence,
    current: LiveSettlementCaptureEvidence,
) -> bool:
    return (
        retained.comment_id == current.comment_id
        and retained.workflow_run_id == current.workflow_run_id
        and retained.comment_created_at == current.comment_created_at
        and retained.provider_generated_at == current.provider_generated_at
        and retained.observed_at == current.observed_at
        and retained.workflow_source_sha == current.workflow_source_sha
        and _canonical_json(retained.receipt) == _canonical_json(current.receipt)
    )


class TrustedSettlementStore:
    """Append-only proof that pilot settlement bytes came from trusted Sportradar transport."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.records_dir = root / "records"
        self.evidence_dir = root / "evidence"
        self.lock_path = root / ".write.lock"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def write_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("trusted settlement store is locked") from exc
        try:
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            os.fsync(fd)
            yield
        finally:
            os.close(fd)
            self.lock_path.unlink(missing_ok=True)
            _fsync_directory(self.root)

    def _record_paths(self) -> list[Path]:
        return sorted(self.records_dir.glob("*.json"))

    def records(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for path in self._record_paths():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"trusted settlement record is invalid: {path.name}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"trusted settlement record is not an object: {path.name}")
            records.append(value)
        return records

    def _store_evidence(self, payload: bytes) -> str:
        digest = _sha256_bytes(payload)
        target = self.evidence_dir / digest
        if target.exists():
            if target.read_bytes() != payload:
                raise RuntimeError(f"trusted settlement evidence collision: {digest}")
            return digest
        _atomic_write(target, payload)
        return digest

    def _append(self, payload: dict[str, object]) -> dict[str, object]:
        records = self.records()
        previous = _ZERO_SHA256 if not records else str(records[-1]["record_sha256"])
        unsigned = dict(payload)
        unsigned["trusted_settlement_version"] = TRUSTED_SETTLEMENT_VERSION
        unsigned["sequence"] = len(records) + 1
        unsigned["previous_record_sha256"] = previous
        digest = _record_sha256(unsigned)
        record = {**unsigned, "record_sha256": digest}
        filename = f"{len(records) + 1:08d}-{digest}.json"
        _atomic_write(self.records_dir / filename, _pretty_json(record))
        return record

    def verify(
        self,
        *,
        pilot_store: ProspectivePilotStore,
        prediction_anchor_store: LivePredictionAnchorStore,
        provider_batch_store: ProviderBatchStore,
        github_get_bytes: GitHubGetBytes | None = None,
        revalidate_live: bool = True,
    ) -> dict[str, object]:
        pilot_report = pilot_store.verify()
        prediction_anchor_store.verify(
            pilot_store=pilot_store,
            github_get_bytes=github_get_bytes,
            revalidate_live=revalidate_live,
        )
        provider_batch_store.verify()
        paths = self._record_paths()
        records = self.records()
        previous = _ZERO_SHA256
        trusted_predictions: set[str] = set()
        comment_ids: set[int] = set()
        run_ids: set[int] = set()
        event_ids: set[str] = set()

        for sequence, record in enumerate(records, start=1):
            if record.get("trusted_settlement_version") != TRUSTED_SETTLEMENT_VERSION:
                raise ValueError(f"unexpected trusted settlement version at {sequence}")
            if record.get("record_type") != "TRUSTED_SETTLEMENT_CAPTURE":
                raise ValueError(f"unexpected trusted settlement type at {sequence}")
            if record.get("settlement_evidence_mode") != TRUSTED_SETTLEMENT_MODE:
                raise ValueError("settlement is not promotion-capable trusted evidence")
            if int(record.get("sequence", -1)) != sequence:
                raise ValueError(f"trusted settlement sequence gap at {sequence}")
            observed_sha = _require_sha256(
                record.get("record_sha256"),
                field=f"trusted_settlement[{sequence}].record_sha256",
            )
            unsigned = dict(record)
            unsigned.pop("record_sha256", None)
            if _record_sha256(unsigned) != observed_sha:
                raise ValueError(f"trusted settlement digest mismatch at {sequence}")
            if record.get("previous_record_sha256") != previous:
                raise ValueError(f"trusted settlement chain mismatch at {sequence}")
            if paths[sequence - 1].name != f"{sequence:08d}-{observed_sha}.json":
                raise ValueError(f"trusted settlement filename mismatch at {sequence}")

            prediction_sha = _require_sha256(
                record.get("prediction_record_sha256"),
                field="prediction_record_sha256",
            )
            prediction = _prediction_record(pilot_store, prediction_sha)
            binding, identity_sha, identity_payload = find_prediction_identity_binding(
                pilot_store=pilot_store,
                prediction=prediction,
            )
            if record.get("identity_binding_sha256") != identity_sha:
                raise ValueError("trusted settlement identity SHA differs from prediction source")
            if revalidate_live:
                authenticate_identity_binding(
                    payload=identity_payload,
                    batch_store=provider_batch_store,
                    github_get_bytes=github_get_bytes,
                )

            comment_id = int(record.get("github_comment_id", -1))
            run_id = int(record.get("workflow_run_id", -1))
            if comment_id <= 0 or run_id <= 0:
                raise ValueError("trusted settlement GitHub identities must be positive")
            evidence_keys = (
                "timeline_sha256",
                "response_headers_sha256",
                "github_comment_response_sha256",
                "workflow_run_response_sha256",
            )
            evidence_hashes = [
                _require_sha256(record.get(key), field=key) for key in evidence_keys
            ]
            if record.get("evidence_sha256") != evidence_hashes:
                raise ValueError("trusted settlement evidence manifest mismatch")
            for digest in evidence_hashes:
                evidence_path = self.evidence_dir / digest
                if not evidence_path.is_file():
                    raise ValueError(f"missing trusted settlement evidence {digest}")
                if _sha256_file(evidence_path) != digest:
                    raise ValueError(f"trusted settlement evidence digest mismatch: {digest}")

            timeline_bytes = (self.evidence_dir / evidence_hashes[0]).read_bytes()
            headers_bytes = (self.evidence_dir / evidence_hashes[1]).read_bytes()
            comment_bytes = (self.evidence_dir / evidence_hashes[2]).read_bytes()
            run_bytes = (self.evidence_dir / evidence_hashes[3]).read_bytes()
            retained = validate_retained_settlement_capture_evidence(
                comment_response_bytes=comment_bytes,
                workflow_run_response_bytes=run_bytes,
                expected_prediction_sha256=prediction_sha,
                expected_identity_sha256=identity_sha,
                expected_event_id=binding.sportradar_event_id,
            )
            if retained.comment_id != comment_id or retained.workflow_run_id != run_id:
                raise ValueError("retained settlement GitHub identity does not reproduce")
            if _sha256_bytes(timeline_bytes) != retained.receipt["timeline_sha256"]:
                raise ValueError("retained timeline SHA differs from trusted receipt")
            if _sha256_bytes(headers_bytes) != retained.receipt["response_headers_sha256"]:
                raise ValueError("retained response-header SHA differs from trusted receipt")
            timeline = _timeline_contract(
                timeline_bytes,
                binding=binding,
                evidence=retained,
            )
            wrapper = _legacy_wrapper(
                prediction=prediction,
                binding=binding,
                evidence=retained,
                timeline=timeline,
            )
            wrapper_bytes = _pretty_json(wrapper)
            settlement = _pilot_settlement(pilot_store, prediction_sha)
            if settlement is None:
                raise ValueError("trusted settlement capture lacks corresponding pilot settlement")
            wrapper_sha = _sha256_bytes(wrapper_bytes)
            if settlement.get("settlement_evidence_sha256") != wrapper_sha:
                raise ValueError("pilot settlement evidence does not reproduce trusted wrapper")
            wrapper_path = pilot_store.evidence_dir / wrapper_sha
            if not wrapper_path.is_file() or wrapper_path.read_bytes() != wrapper_bytes:
                raise ValueError("pilot settlement wrapper bytes do not reproduce")
            if record.get("pilot_settlement_record_sha256") != settlement.get("record_sha256"):
                raise ValueError("trusted settlement does not reference exact pilot settlement")

            if revalidate_live:
                current = fetch_authenticated_settlement_capture_evidence(
                    comment_id=comment_id,
                    expected_prediction_sha256=prediction_sha,
                    expected_identity_sha256=identity_sha,
                    expected_event_id=binding.sportradar_event_id,
                    get_bytes=github_get_bytes,
                )
                if not _same_commitment(retained, current):
                    raise ValueError(
                        "live GitHub settlement commitment differs from retained evidence"
                    )

            event_id = binding.sportradar_event_id
            if prediction_sha in trusted_predictions:
                raise ValueError("prediction has more than one trusted settlement")
            if comment_id in comment_ids:
                raise ValueError("GitHub settlement comment is reused")
            if run_id in run_ids:
                raise ValueError("GitHub settlement workflow run is reused")
            if event_id in event_ids:
                raise ValueError("Sportradar event is reused across trusted settlements")
            trusted_predictions.add(prediction_sha)
            comment_ids.add(comment_id)
            run_ids.add(run_id)
            event_ids.add(event_id)
            previous = observed_sha

        all_settlements = {
            str(record.get("prediction_record_sha256"))
            for record in pilot_store.records()
            if record.get("record_type") == "SETTLEMENT"
        }
        missing = sorted(all_settlements - trusted_predictions)
        if missing:
            raise ValueError(
                "pilot settlements lack trusted Sportradar transport: " + ", ".join(missing)
            )
        if trusted_predictions - all_settlements:
            raise ValueError("trusted settlement store contains an unsettled prediction")

        primary_count = sum(
            1
            for record in pilot_store.records()
            if record.get("record_type") == "SETTLEMENT"
            and bool(record.get("primary_evaluation_eligible"))
        )
        return {
            "trusted_settlement_version": TRUSTED_SETTLEMENT_VERSION,
            "pilot_chain_head_sha256": pilot_report["chain_head_sha256"],
            "record_count": len(records),
            "trusted_settlement_count": len(trusted_predictions),
            "primary_evaluation_eligible_count": primary_count,
            "chain_head_sha256": previous,
            "revalidated_live": revalidate_live,
            "status": "LIVE_VERIFIED" if revalidate_live else "RETAINED_VERIFIED",
        }


def admit_trusted_settlement(
    *,
    pilot_store: ProspectivePilotStore,
    prediction_anchor_store: LivePredictionAnchorStore,
    provider_batch_store: ProviderBatchStore,
    trusted_store: TrustedSettlementStore,
    prediction_record_sha256: str,
    github_comment_id: int,
    timeline_path: Path,
    response_headers_path: Path,
    github_get_bytes: GitHubGetBytes | None = None,
) -> dict[str, object]:
    """Authenticate transport and identity, settle pilot, then append trusted sidecar proof."""

    with trusted_store.write_lock():
        trusted_store.verify(
            pilot_store=pilot_store,
            prediction_anchor_store=prediction_anchor_store,
            provider_batch_store=provider_batch_store,
            github_get_bytes=github_get_bytes,
            revalidate_live=True,
        )
        prediction = _prediction_record(pilot_store, prediction_record_sha256)
        binding, identity_sha, identity_payload = find_prediction_identity_binding(
            pilot_store=pilot_store,
            prediction=prediction,
        )
        authenticate_identity_binding(
            payload=identity_payload,
            batch_store=provider_batch_store,
            github_get_bytes=github_get_bytes,
        )
        if any(
            record.get("prediction_record_sha256") == prediction_record_sha256
            for record in trusted_store.records()
        ):
            raise ValueError("prediction already has a trusted settlement capture")

        evidence = fetch_authenticated_settlement_capture_evidence(
            comment_id=github_comment_id,
            expected_prediction_sha256=prediction_record_sha256,
            expected_identity_sha256=identity_sha,
            expected_event_id=binding.sportradar_event_id,
            get_bytes=github_get_bytes,
        )
        timeline_bytes = timeline_path.read_bytes()
        headers_bytes = response_headers_path.read_bytes()
        if _sha256_bytes(timeline_bytes) != evidence.receipt["timeline_sha256"]:
            raise ValueError("provided timeline does not match trusted settlement receipt")
        if _sha256_bytes(headers_bytes) != evidence.receipt["response_headers_sha256"]:
            raise ValueError("provided response headers do not match trusted settlement receipt")
        timeline = _timeline_contract(
            timeline_bytes,
            binding=binding,
            evidence=evidence,
        )
        wrapper = _legacy_wrapper(
            prediction=prediction,
            binding=binding,
            evidence=evidence,
            timeline=timeline,
        )
        wrapper_bytes = _pretty_json(wrapper)
        wrapper_sha = _sha256_bytes(wrapper_bytes)

        pilot_settlement = _pilot_settlement(pilot_store, prediction_record_sha256)
        if pilot_settlement is None:
            with tempfile.TemporaryDirectory() as temp_dir:
                wrapper_path = Path(temp_dir) / "trusted-settlement-wrapper.json"
                wrapper_path.write_bytes(wrapper_bytes)
                pilot_settlement = settle_prediction(
                    store=pilot_store,
                    prediction_record_sha256=prediction_record_sha256,
                    settlement_evidence_path=wrapper_path,
                )
        else:
            if pilot_settlement.get("settlement_evidence_sha256") != wrapper_sha:
                raise ValueError(
                    "existing pilot settlement differs from authenticated transport evidence"
                )
            retained_wrapper = pilot_store.evidence_dir / wrapper_sha
            if not retained_wrapper.is_file() or retained_wrapper.read_bytes() != wrapper_bytes:
                raise ValueError("existing pilot settlement wrapper bytes do not reproduce")

        timeline_sha = trusted_store._store_evidence(timeline_bytes)
        headers_sha = trusted_store._store_evidence(headers_bytes)
        comment_sha = trusted_store._store_evidence(evidence.comment_response_bytes)
        run_sha = trusted_store._store_evidence(evidence.workflow_run_response_bytes)
        return trusted_store._append(
            {
                "record_type": "TRUSTED_SETTLEMENT_CAPTURE",
                "settlement_evidence_mode": TRUSTED_SETTLEMENT_MODE,
                "prediction_record_sha256": prediction_record_sha256,
                "prediction_id": prediction["prediction_id"],
                "match_id": prediction["match_id"],
                "tour": prediction["tour"],
                "identity_binding_sha256": identity_sha,
                "sportradar_event_id": binding.sportradar_event_id,
                "pilot_settlement_record_sha256": pilot_settlement["record_sha256"],
                "github_comment_id": evidence.comment_id,
                "workflow_run_id": evidence.workflow_run_id,
                "workflow_source_sha": evidence.workflow_source_sha,
                "provider_generated_at": evidence.provider_generated_at.isoformat(),
                "observed_at": evidence.observed_at.isoformat(),
                "timeline_sha256": timeline_sha,
                "response_headers_sha256": headers_sha,
                "github_comment_response_sha256": comment_sha,
                "workflow_run_response_sha256": run_sha,
                "evidence_sha256": [timeline_sha, headers_sha, comment_sha, run_sha],
            }
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promotion-capable trusted Sportradar settlement transport"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    admit = subparsers.add_parser("admit")
    admit.add_argument("--pilot-store", required=True, type=Path)
    admit.add_argument("--prediction-anchor-store", required=True, type=Path)
    admit.add_argument("--provider-batch-store", required=True, type=Path)
    admit.add_argument("--trusted-settlement-store", required=True, type=Path)
    admit.add_argument("--prediction-record-sha256", required=True)
    admit.add_argument("--github-comment-id", required=True, type=int)
    admit.add_argument("--timeline", required=True, type=Path)
    admit.add_argument("--response-headers", required=True, type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--pilot-store", required=True, type=Path)
    verify.add_argument("--prediction-anchor-store", required=True, type=Path)
    verify.add_argument("--provider-batch-store", required=True, type=Path)
    verify.add_argument("--trusted-settlement-store", required=True, type=Path)
    verify.add_argument("--retained-only", action="store_true")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    pilot = ProspectivePilotStore(args.pilot_store)
    anchors = LivePredictionAnchorStore(args.prediction_anchor_store)
    batches = ProviderBatchStore(args.provider_batch_store)
    trusted = TrustedSettlementStore(args.trusted_settlement_store)
    if args.command == "admit":
        result = admit_trusted_settlement(
            pilot_store=pilot,
            prediction_anchor_store=anchors,
            provider_batch_store=batches,
            trusted_store=trusted,
            prediction_record_sha256=args.prediction_record_sha256,
            github_comment_id=args.github_comment_id,
            timeline_path=args.timeline,
            response_headers_path=args.response_headers,
        )
    else:
        result = trusted.verify(
            pilot_store=pilot,
            prediction_anchor_store=anchors,
            provider_batch_store=batches,
            revalidate_live=not args.retained_only,
        )
    print(_pretty_json(result).decode("utf-8"), end="")


if __name__ == "__main__":
    main()
