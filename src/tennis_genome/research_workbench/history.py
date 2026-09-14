from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord
from .evaluation import EvaluationResult
from .lineage import CanonicalEvaluationBinding, ProcedureSearchFamily
from .protected import ProtectedOpenReceipt

_ZERO_SHA256 = "0" * 64
_SCHEMA_VERSION = "tennis-workbench-research-history-v1"

EventType = Literal[
    "PROCEDURE_REGISTERED",
    "EVALUATION_REGISTERED",
    "SEARCH_FAMILY_REGISTERED",
    "SEARCH_FAMILY_FROZEN",
    "PROTECTED_OPENED",
    "RESULT_RECORDED",
    "EVALUATION_CLOSED",
    "EVALUATION_INVALIDATED",
]
EvaluationVerdict = Literal[
    "PROMOTED",
    "NO_IMPROVEMENT",
    "FAILED",
    "INCONCLUSIVE",
]


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_sha256(value: str, *, label: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{label} must be lowercase SHA-256")
    return value


class ResearchHistoryEvent(WorkbenchRecord):
    schema_version: Literal["tennis-workbench-research-history-v1"] = _SCHEMA_VERSION
    sequence: int
    timestamp_utc: str
    event_type: EventType
    subject_id: str
    subject_sha256: str
    previous_event_sha256: str
    details_json: str

    @field_validator("subject_id")
    @classmethod
    def _subject_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("research-history subject_id must be nonblank")
        return value

    @field_validator("subject_sha256", "previous_event_sha256")
    @classmethod
    def _digest(cls, value: str) -> str:
        return _validate_sha256(value, label="research-history digest")

    @field_validator("timestamp_utc")
    @classmethod
    def _utc_timestamp(cls, value: str) -> str:
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("timestamp_utc must be ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp_utc must be timezone-aware")
        if parsed.utcoffset().total_seconds() != 0:
            raise ValueError("timestamp_utc must be UTC")
        return parsed.astimezone(UTC).isoformat()

    @field_validator("details_json")
    @classmethod
    def _canonical_details(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("details_json must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("details_json must encode a JSON object")
        return _canonical_json(parsed)

    @model_validator(mode="after")
    def _sequence_positive(self) -> ResearchHistoryEvent:
        if self.sequence <= 0:
            raise ValueError("research-history sequence must be positive")
        return self

    @property
    def details(self) -> dict[str, object]:
        value = json.loads(self.details_json)
        if not isinstance(value, dict):
            raise AssertionError("validated event details stopped being an object")
        return value


class ResearchLifecycleAudit(WorkbenchRecord):
    status: Literal["PASS", "EMPTY"]
    event_count: int
    procedure_count: int
    evaluation_count: int
    family_count: int
    protected_open_count: int
    result_count: int
    closed_evaluation_count: int
    invalidated_evaluation_count: int
    chain_head_sha256: str


class _LifecycleState:
    def __init__(self) -> None:
        self.procedures: dict[str, ForecastingProcedureSpec] = {}
        self.evaluations: dict[str, EvaluationSpec] = {}
        self.families: dict[str, ProcedureSearchFamily] = {}
        self.protected_opened: set[str] = set()
        self.results: dict[tuple[str, str], EvaluationResult] = {}
        self.closed: dict[str, EvaluationVerdict] = {}
        self.invalidated: set[str] = set()


def _procedure_from(details: dict[str, object]) -> ForecastingProcedureSpec:
    payload = details.get("procedure")
    if not isinstance(payload, dict):
        raise ValueError("procedure registration lacks canonical procedure payload")
    return ForecastingProcedureSpec(**payload)


def _evaluation_from(details: dict[str, object]) -> EvaluationSpec:
    payload = details.get("evaluation")
    if not isinstance(payload, dict):
        raise ValueError("evaluation registration lacks canonical evaluation payload")
    return EvaluationSpec(**payload)


def _family_from(details: dict[str, object]) -> ProcedureSearchFamily:
    payload = details.get("family")
    if not isinstance(payload, dict):
        raise ValueError("family event lacks canonical family payload")
    return ProcedureSearchFamily(**payload)


def _result_from(details: dict[str, object]) -> EvaluationResult:
    payload = details.get("result")
    if not isinstance(payload, dict):
        raise ValueError("result event lacks canonical result payload")
    return EvaluationResult(**payload)


def _binding_from(details: dict[str, object]) -> CanonicalEvaluationBinding:
    payload = details.get("binding")
    if not isinstance(payload, dict):
        raise ValueError("result event lacks canonical binding payload")
    return CanonicalEvaluationBinding(**payload)


def _same_family_declaration(
    left: ProcedureSearchFamily,
    right: ProcedureSearchFamily,
) -> bool:
    left_payload = left.canonical_payload()
    right_payload = right.canonical_payload()
    left_payload.pop("frozen", None)
    right_payload.pop("frozen", None)
    return left_payload == right_payload


def _apply_event(state: _LifecycleState, event: ResearchHistoryEvent) -> None:
    details = event.details

    if event.event_type == "PROCEDURE_REGISTERED":
        procedure = _procedure_from(details)
        if procedure.procedure_id != event.subject_id:
            raise ValueError("procedure registration subject identity mismatch")
        if procedure.semantic_sha256 != event.subject_sha256:
            raise ValueError("procedure registration digest mismatch")
        if procedure.procedure_id in state.procedures:
            raise ValueError("procedure registered more than once")
        state.procedures[procedure.procedure_id] = procedure
        return

    if event.event_type == "EVALUATION_REGISTERED":
        evaluation = _evaluation_from(details)
        if evaluation.evaluation_id != event.subject_id:
            raise ValueError("evaluation registration subject identity mismatch")
        if evaluation.semantic_sha256 != event.subject_sha256:
            raise ValueError("evaluation registration digest mismatch")
        if evaluation.evaluation_id in state.evaluations:
            raise ValueError("evaluation registered more than once")
        missing = sorted(set(evaluation.procedure_ids) - set(state.procedures))
        if missing:
            raise ValueError(
                "evaluation references unregistered procedures: " + ", ".join(missing)
            )
        state.evaluations[evaluation.evaluation_id] = evaluation
        return

    if event.event_type == "SEARCH_FAMILY_REGISTERED":
        family = _family_from(details)
        if family.family_id != event.subject_id:
            raise ValueError("search-family registration subject identity mismatch")
        if family.semantic_sha256 != event.subject_sha256:
            raise ValueError("search-family registration digest mismatch")
        if family.frozen:
            raise ValueError("search family must be registered before it is frozen")
        if family.family_id in state.families:
            raise ValueError("search family registered more than once")
        missing = sorted(set(family.procedure_ids) - set(state.procedures))
        if missing:
            raise ValueError(
                "search family references unregistered procedures: " + ", ".join(missing)
            )
        state.families[family.family_id] = family
        return

    if event.event_type == "SEARCH_FAMILY_FROZEN":
        frozen = _family_from(details)
        current = state.families.get(event.subject_id)
        if current is None:
            raise ValueError("cannot freeze an unregistered search family")
        if current.frozen:
            raise ValueError("search family frozen more than once")
        if not frozen.frozen:
            raise ValueError("search-family freeze event must contain frozen=True")
        if not _same_family_declaration(current, frozen):
            raise ValueError("search family changed while being frozen")
        if frozen.semantic_sha256 != event.subject_sha256:
            raise ValueError("search-family frozen digest mismatch")
        reason = str(details.get("reason", "")).strip()
        if not reason:
            raise ValueError("search-family freeze requires a reason")
        state.families[event.subject_id] = frozen
        return

    if event.event_type == "PROTECTED_OPENED":
        receipt_payload = details.get("receipt")
        if not isinstance(receipt_payload, dict):
            raise ValueError("protected-open event lacks receipt")
        receipt = ProtectedOpenReceipt(**receipt_payload)
        evaluation = state.evaluations.get(receipt.evaluation_id)
        if evaluation is None:
            raise ValueError("protected open references unregistered evaluation")
        if evaluation.evaluation_role != "PROTECTED":
            raise ValueError("protected open references a development evaluation")
        if receipt.evaluation_id in state.protected_opened:
            raise ValueError("protected evaluation opened more than once")
        if tuple(receipt.procedure_ids) != tuple(evaluation.procedure_ids):
            raise ValueError("protected receipt procedure family differs from evaluation")
        if _sha256_json(asdict(receipt)) != event.subject_sha256:
            raise ValueError("protected-open receipt digest mismatch")
        state.protected_opened.add(receipt.evaluation_id)
        return

    if event.event_type == "RESULT_RECORDED":
        result = _result_from(details)
        binding = _binding_from(details)
        key = (result.evaluation_id, result.procedure_id)
        evaluation = state.evaluations.get(result.evaluation_id)
        procedure = state.procedures.get(result.procedure_id)
        if evaluation is None or procedure is None:
            raise ValueError("result references unregistered evaluation or procedure")
        if result.evaluation_id in state.closed:
            raise ValueError("result recorded after evaluation closure")
        if key in state.results:
            raise ValueError("procedure result recorded more than once")
        if result.evaluation_spec_sha256 != evaluation.semantic_sha256:
            raise ValueError("result evaluation-spec digest mismatch")
        if result.procedure_spec_sha256 != procedure.semantic_sha256:
            raise ValueError("result procedure-spec digest mismatch")
        if binding.evaluation_spec_sha256 != evaluation.semantic_sha256:
            raise ValueError("binding evaluation-spec digest mismatch")
        if binding.procedure_spec_sha256 != procedure.semantic_sha256:
            raise ValueError("binding procedure-spec digest mismatch")
        if evaluation.evaluation_role == "PROTECTED":
            if evaluation.evaluation_id not in state.protected_opened:
                raise ValueError("protected result recorded before irreversible open")
        if result.semantic_sha256 != event.subject_sha256:
            raise ValueError("result event digest mismatch")
        state.results[key] = result
        return

    if event.event_type == "EVALUATION_CLOSED":
        evaluation = state.evaluations.get(event.subject_id)
        if evaluation is None:
            raise ValueError("close references unregistered evaluation")
        if evaluation.semantic_sha256 != event.subject_sha256:
            raise ValueError("close evaluation digest mismatch")
        if evaluation.evaluation_id in state.closed:
            raise ValueError("evaluation closed more than once")
        verdict = str(details.get("verdict", "")).strip()
        if verdict not in {"PROMOTED", "NO_IMPROVEMENT", "FAILED", "INCONCLUSIVE"}:
            raise ValueError("unsupported evaluation verdict")
        reason = str(details.get("reason", "")).strip()
        if not reason:
            raise ValueError("evaluation closure requires a reason")
        missing_results = [
            procedure_id
            for procedure_id in evaluation.procedure_ids
            if (evaluation.evaluation_id, procedure_id) not in state.results
        ]
        if missing_results:
            raise ValueError(
                "evaluation cannot close before every registered procedure has a result: "
                + ", ".join(missing_results)
            )
        state.closed[evaluation.evaluation_id] = verdict  # type: ignore[assignment]
        return

    if event.event_type == "EVALUATION_INVALIDATED":
        evaluation = state.evaluations.get(event.subject_id)
        if evaluation is None:
            raise ValueError("invalidation references unregistered evaluation")
        if evaluation.semantic_sha256 != event.subject_sha256:
            raise ValueError("invalidation evaluation digest mismatch")
        if evaluation.evaluation_id not in state.closed:
            raise ValueError("evaluation must be closed before invalidation")
        if evaluation.evaluation_id in state.invalidated:
            raise ValueError("evaluation invalidated more than once")
        reason = str(details.get("reason", "")).strip()
        if not reason:
            raise ValueError("evaluation invalidation requires a reason")
        state.invalidated.add(evaluation.evaluation_id)
        return

    raise AssertionError(f"unsupported research-history event: {event.event_type}")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class ResearchLifecycleLedger:
    """Atomic append-only black-box recorder for Workbench research lifecycle."""

    def __init__(
        self,
        root: Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root)
        self.events_dir = self.root / "events"
        self.lock_path = self.root / ".write.lock"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(UTC))

    @contextmanager
    def _write_lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("research lifecycle ledger is already being written") from exc
        try:
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            os.fsync(fd)
            yield
        finally:
            os.close(fd)
            self.lock_path.unlink(missing_ok=True)

    def _paths(self) -> list[Path]:
        return sorted(self.events_dir.glob("*.json"))

    def events(self) -> tuple[ResearchHistoryEvent, ...]:
        events: list[ResearchHistoryEvent] = []
        for path in self._paths():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"research-history event is not an object: {path.name}")
            supplied = str(payload.get("semantic_sha256", ""))
            raw_event = payload.get("event")
            if not isinstance(raw_event, dict):
                raise ValueError(f"research-history event payload missing: {path.name}")
            event = ResearchHistoryEvent(**raw_event)
            if event.semantic_sha256 != supplied:
                raise ValueError(f"research-history event digest mismatch: {path.name}")
            expected_name = f"{event.sequence:08d}-{event.semantic_sha256}.json"
            if path.name != expected_name:
                raise ValueError(f"research-history filename mismatch: {path.name}")
            events.append(event)
        return tuple(events)

    def _reconstruct(self) -> tuple[_LifecycleState, tuple[ResearchHistoryEvent, ...]]:
        state = _LifecycleState()
        events = self.events()
        previous = _ZERO_SHA256
        for expected_sequence, event in enumerate(events, start=1):
            if event.sequence != expected_sequence:
                raise ValueError(
                    f"research-history sequence gap at {expected_sequence}"
                )
            if event.previous_event_sha256 != previous:
                raise ValueError(
                    f"research-history hash chain mismatch at {expected_sequence}"
                )
            _apply_event(state, event)
            previous = event.semantic_sha256
        return state, events

    def verify(self) -> ResearchLifecycleAudit:
        state, events = self._reconstruct()
        chain_head = events[-1].semantic_sha256 if events else _ZERO_SHA256
        return ResearchLifecycleAudit(
            status="PASS" if events else "EMPTY",
            event_count=len(events),
            procedure_count=len(state.procedures),
            evaluation_count=len(state.evaluations),
            family_count=len(state.families),
            protected_open_count=len(state.protected_opened),
            result_count=len(state.results),
            closed_evaluation_count=len(state.closed),
            invalidated_evaluation_count=len(state.invalidated),
            chain_head_sha256=chain_head,
        )

    def _append(
        self,
        *,
        event_type: EventType,
        subject_id: str,
        subject_sha256: str,
        details: dict[str, object],
    ) -> ResearchHistoryEvent:
        with self._write_lock():
            state, events = self._reconstruct()
            now = self._now()
            if now.tzinfo is None or now.utcoffset() is None:
                raise RuntimeError("research-history clock must be timezone-aware")
            event = ResearchHistoryEvent(
                sequence=len(events) + 1,
                timestamp_utc=now.astimezone(UTC).isoformat(),
                event_type=event_type,
                subject_id=subject_id,
                subject_sha256=subject_sha256,
                previous_event_sha256=(
                    events[-1].semantic_sha256 if events else _ZERO_SHA256
                ),
                details_json=_canonical_json(details),
            )
            _apply_event(state, event)
            wrapper = {
                "semantic_sha256": event.semantic_sha256,
                "event": event.canonical_payload(),
            }
            payload = (_canonical_json(wrapper) + "\n").encode("utf-8")
            target = self.events_dir / (
                f"{event.sequence:08d}-{event.semantic_sha256}.json"
            )
            _atomic_write(target, payload)
            return event

    def register_procedure(
        self,
        procedure: ForecastingProcedureSpec,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="PROCEDURE_REGISTERED",
            subject_id=procedure.procedure_id,
            subject_sha256=procedure.semantic_sha256,
            details={"procedure": procedure.canonical_payload()},
        )

    def register_evaluation(
        self,
        evaluation: EvaluationSpec,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="EVALUATION_REGISTERED",
            subject_id=evaluation.evaluation_id,
            subject_sha256=evaluation.semantic_sha256,
            details={"evaluation": evaluation.canonical_payload()},
        )

    def register_search_family(
        self,
        family: ProcedureSearchFamily,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="SEARCH_FAMILY_REGISTERED",
            subject_id=family.family_id,
            subject_sha256=family.semantic_sha256,
            details={"family": family.canonical_payload()},
        )

    def freeze_search_family(
        self,
        family: ProcedureSearchFamily,
        *,
        reason: str,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="SEARCH_FAMILY_FROZEN",
            subject_id=family.family_id,
            subject_sha256=family.semantic_sha256,
            details={
                "family": family.canonical_payload(),
                "reason": reason,
            },
        )

    def record_protected_open(
        self,
        receipt: ProtectedOpenReceipt,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="PROTECTED_OPENED",
            subject_id=receipt.evaluation_id,
            subject_sha256=_sha256_json(asdict(receipt)),
            details={"receipt": asdict(receipt)},
        )

    def record_result(
        self,
        result: EvaluationResult,
        *,
        binding: CanonicalEvaluationBinding,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="RESULT_RECORDED",
            subject_id=f"{result.evaluation_id}::{result.procedure_id}",
            subject_sha256=result.semantic_sha256,
            details={
                "result": result.canonical_payload(),
                "binding": binding.canonical_payload(),
            },
        )

    def close_evaluation(
        self,
        evaluation: EvaluationSpec,
        *,
        verdict: EvaluationVerdict,
        reason: str,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="EVALUATION_CLOSED",
            subject_id=evaluation.evaluation_id,
            subject_sha256=evaluation.semantic_sha256,
            details={
                "verdict": verdict,
                "reason": reason,
            },
        )

    def invalidate_evaluation(
        self,
        evaluation: EvaluationSpec,
        *,
        reason: str,
    ) -> ResearchHistoryEvent:
        return self._append(
            event_type="EVALUATION_INVALIDATED",
            subject_id=evaluation.evaluation_id,
            subject_sha256=evaluation.semantic_sha256,
            details={"reason": reason},
        )
