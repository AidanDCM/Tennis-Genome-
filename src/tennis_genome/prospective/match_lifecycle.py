from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

MATCH_LIFECYCLE_VERSION = "tennis-genome-match-lifecycle-v1"
_ZERO_SHA256 = "0" * 64

MatchLifecycleState = Literal[
    "DISCOVERED",
    "SNAPSHOT_CAPTURED",
    "CHAMPION_PREDICTED",
    "CHAMPION_ANCHORED",
    "CHALLENGERS_PREDICTED",
    "CHALLENGERS_ANCHORED",
    "RESULT_CAPTURED",
    "SETTLED",
    "SCORED",
    "VALIDATED",
]

_NEXT_STATE: dict[MatchLifecycleState, MatchLifecycleState | None] = {
    "DISCOVERED": "SNAPSHOT_CAPTURED",
    "SNAPSHOT_CAPTURED": "CHAMPION_PREDICTED",
    "CHAMPION_PREDICTED": "CHAMPION_ANCHORED",
    "CHAMPION_ANCHORED": "CHALLENGERS_PREDICTED",
    "CHALLENGERS_PREDICTED": "CHALLENGERS_ANCHORED",
    "CHALLENGERS_ANCHORED": "RESULT_CAPTURED",
    "RESULT_CAPTURED": "SETTLED",
    "SETTLED": "SCORED",
    "SCORED": "VALIDATED",
    "VALIDATED": None,
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@dataclass(frozen=True)
class MatchLifecycleEvent:
    sequence: int
    timestamp_utc: str
    lifecycle_id: str
    match_id: str
    provider_event_id: str
    state: MatchLifecycleState
    evidence_sha256: tuple[str, ...]
    previous_event_sha256: str
    details_json: str

    @property
    def details(self) -> dict[str, object]:
        value = json.loads(self.details_json)
        if not isinstance(value, dict):
            raise ValueError("match lifecycle details must decode to an object")
        return value

    @property
    def semantic_sha256(self) -> str:
        return _sha256_text(_canonical_json(asdict(self)))


@dataclass(frozen=True)
class MatchLifecycleAudit:
    status: Literal["EMPTY", "PASS"]
    event_count: int
    lifecycle_count: int
    validated_count: int
    chain_head_sha256: str
    lifecycle_states: dict[str, MatchLifecycleState]


class _LifecycleState:
    def __init__(self) -> None:
        self.by_lifecycle: dict[str, MatchLifecycleEvent] = {}
        self.match_to_lifecycle: dict[str, str] = {}
        self.provider_to_lifecycle: dict[str, str] = {}


def _validate_identity(
    *,
    lifecycle_id: str,
    match_id: str,
    provider_event_id: str,
) -> None:
    if not lifecycle_id.strip():
        raise ValueError("lifecycle_id must be non-empty")
    if not match_id.strip():
        raise ValueError("match_id must be non-empty")
    if not provider_event_id.strip():
        raise ValueError("provider_event_id must be non-empty")


def _validate_evidence(evidence_sha256: tuple[str, ...]) -> None:
    if not evidence_sha256:
        raise ValueError("match lifecycle event requires evidence")
    if len(set(evidence_sha256)) != len(evidence_sha256):
        raise ValueError("match lifecycle evidence SHA values must be unique")
    for digest in evidence_sha256:
        if not _valid_sha256(digest):
            raise ValueError("match lifecycle evidence must be lowercase SHA-256")


def _apply_event(state: _LifecycleState, event: MatchLifecycleEvent) -> None:
    _validate_identity(
        lifecycle_id=event.lifecycle_id,
        match_id=event.match_id,
        provider_event_id=event.provider_event_id,
    )
    _validate_evidence(event.evidence_sha256)

    current = state.by_lifecycle.get(event.lifecycle_id)
    if current is None:
        if event.state != "DISCOVERED":
            raise ValueError("new match lifecycle must begin at DISCOVERED")
        if event.match_id in state.match_to_lifecycle:
            raise ValueError("match_id is already bound to another lifecycle")
        if event.provider_event_id in state.provider_to_lifecycle:
            raise ValueError("provider_event_id is already bound to another lifecycle")
        state.match_to_lifecycle[event.match_id] = event.lifecycle_id
        state.provider_to_lifecycle[event.provider_event_id] = event.lifecycle_id
        state.by_lifecycle[event.lifecycle_id] = event
        return

    if event.match_id != current.match_id:
        raise ValueError("match lifecycle match_id changed")
    if event.provider_event_id != current.provider_event_id:
        raise ValueError("match lifecycle provider_event_id changed")

    expected = _NEXT_STATE[current.state]
    if expected is None:
        raise ValueError("validated match lifecycle cannot advance")
    if event.state != expected:
        raise ValueError(
            f"illegal match lifecycle transition: {current.state} -> {event.state}; "
            f"expected {expected}"
        )
    state.by_lifecycle[event.lifecycle_id] = event


class MatchLifecycleLedger:
    """Append-only event ledger for prospective match prediction lifecycles."""

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
    def _write_lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("match lifecycle ledger is already being written") from exc
        try:
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            os.fsync(fd)
            yield
        finally:
            os.close(fd)
            self.lock_path.unlink(missing_ok=True)

    def _paths(self) -> list[Path]:
        return sorted(self.events_dir.glob("*.json"))

    def events(self) -> tuple[MatchLifecycleEvent, ...]:
        result: list[MatchLifecycleEvent] = []
        for path in self._paths():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"match lifecycle event is not an object: {path.name}")
            if payload.get("lifecycle_version") != MATCH_LIFECYCLE_VERSION:
                raise ValueError(f"unexpected match lifecycle version: {path.name}")
            event_payload = payload.get("event")
            if not isinstance(event_payload, dict):
                raise ValueError(f"match lifecycle event payload missing: {path.name}")
            event_payload = dict(event_payload)
            evidence = event_payload.get("evidence_sha256")
            if not isinstance(evidence, list):
                raise ValueError(f"match lifecycle evidence list missing: {path.name}")
            event_payload["evidence_sha256"] = tuple(str(item) for item in evidence)
            event = MatchLifecycleEvent(**event_payload)
            supplied = str(payload.get("semantic_sha256", ""))
            if event.semantic_sha256 != supplied:
                raise ValueError(f"match lifecycle digest mismatch: {path.name}")
            expected_name = f"{event.sequence:08d}-{event.semantic_sha256}.json"
            if path.name != expected_name:
                raise ValueError(f"match lifecycle filename mismatch: {path.name}")
            result.append(event)
        return tuple(result)

    def _reconstruct(self) -> tuple[_LifecycleState, tuple[MatchLifecycleEvent, ...]]:
        state = _LifecycleState()
        events = self.events()
        previous = _ZERO_SHA256
        for expected_sequence, event in enumerate(events, start=1):
            if event.sequence != expected_sequence:
                raise ValueError(f"match lifecycle sequence gap at {expected_sequence}")
            if event.previous_event_sha256 != previous:
                raise ValueError(
                    f"match lifecycle hash chain mismatch at {expected_sequence}"
                )
            _apply_event(state, event)
            previous = event.semantic_sha256
        return state, events

    def verify(self) -> MatchLifecycleAudit:
        state, events = self._reconstruct()
        states = {
            lifecycle_id: event.state
            for lifecycle_id, event in sorted(state.by_lifecycle.items())
        }
        return MatchLifecycleAudit(
            status="PASS" if events else "EMPTY",
            event_count=len(events),
            lifecycle_count=len(states),
            validated_count=sum(value == "VALIDATED" for value in states.values()),
            chain_head_sha256=events[-1].semantic_sha256 if events else _ZERO_SHA256,
            lifecycle_states=states,
        )

    def _append(
        self,
        *,
        lifecycle_id: str,
        match_id: str,
        provider_event_id: str,
        state_value: MatchLifecycleState,
        evidence_sha256: tuple[str, ...],
        details: dict[str, object],
    ) -> MatchLifecycleEvent:
        with self._write_lock():
            reconstructed, events = self._reconstruct()
            now = self._now()
            if now.tzinfo is None or now.utcoffset() is None:
                raise RuntimeError("match lifecycle clock must be timezone-aware")
            event = MatchLifecycleEvent(
                sequence=len(events) + 1,
                timestamp_utc=now.astimezone(UTC).isoformat(),
                lifecycle_id=lifecycle_id,
                match_id=match_id,
                provider_event_id=provider_event_id,
                state=state_value,
                evidence_sha256=evidence_sha256,
                previous_event_sha256=(
                    events[-1].semantic_sha256 if events else _ZERO_SHA256
                ),
                details_json=_canonical_json(details),
            )
            _apply_event(reconstructed, event)
            wrapper = {
                "lifecycle_version": MATCH_LIFECYCLE_VERSION,
                "semantic_sha256": event.semantic_sha256,
                "event": asdict(event),
            }
            payload = (_canonical_json(wrapper) + "\n").encode("utf-8")
            target = self.events_dir / (
                f"{event.sequence:08d}-{event.semantic_sha256}.json"
            )
            _atomic_write(target, payload)
            return event

    def discover(
        self,
        *,
        lifecycle_id: str,
        match_id: str,
        provider_event_id: str,
        evidence_sha256: tuple[str, ...],
        details: dict[str, object] | None = None,
    ) -> MatchLifecycleEvent:
        return self._append(
            lifecycle_id=lifecycle_id,
            match_id=match_id,
            provider_event_id=provider_event_id,
            state_value="DISCOVERED",
            evidence_sha256=evidence_sha256,
            details=details or {},
        )

    def advance(
        self,
        *,
        lifecycle_id: str,
        state: MatchLifecycleState,
        evidence_sha256: tuple[str, ...],
        details: dict[str, object] | None = None,
    ) -> MatchLifecycleEvent:
        reconstructed, _ = self._reconstruct()
        current = reconstructed.by_lifecycle.get(lifecycle_id)
        if current is None:
            raise ValueError("cannot advance an undiscovered match lifecycle")
        return self._append(
            lifecycle_id=lifecycle_id,
            match_id=current.match_id,
            provider_event_id=current.provider_event_id,
            state_value=state,
            evidence_sha256=evidence_sha256,
            details=details or {},
        )
