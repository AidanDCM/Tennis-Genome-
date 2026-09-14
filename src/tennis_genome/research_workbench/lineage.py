from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import field_validator, model_validator

from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord

_ZERO_SHA256 = "0" * 64


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


class DatasetFingerprint(WorkbenchRecord):
    """Fail-closed identity for one ordered tennis evaluation population."""

    dataset_id: str
    row_count: int
    first_event_time: str
    last_event_time: str
    row_identity_sha256: str
    source_manifest_sha256: str
    availability_contract_sha256: str
    schema_version: str
    sha256: str

    @field_validator(
        "row_identity_sha256",
        "source_manifest_sha256",
        "availability_contract_sha256",
        "sha256",
    )
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("fingerprint digests must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _verify_digest(self) -> "DatasetFingerprint":
        if self.row_count <= 0:
            raise ValueError("dataset fingerprint requires at least one row")
        expected = _sha256(
            {
                "kind": "tennis-workbench-dataset-v1",
                "dataset_id": self.dataset_id,
                "row_count": self.row_count,
                "first_event_time": self.first_event_time,
                "last_event_time": self.last_event_time,
                "row_identity_sha256": self.row_identity_sha256,
                "source_manifest_sha256": self.source_manifest_sha256,
                "availability_contract_sha256": self.availability_contract_sha256,
                "schema_version": self.schema_version,
            }
        )
        if self.sha256 != expected:
            raise ValueError("dataset fingerprint digest does not reproduce")
        return self


def fingerprint_match_population(
    *,
    dataset_id: str,
    ordered_rows: Sequence[Mapping[str, Any]],
    source_manifest_sha256: str,
    availability_contract_sha256: str,
    schema_version: str,
) -> DatasetFingerprint:
    """Fingerprint an exact ordered match population.

    Each row must expose unique match_id and an event_time string. The order supplied
    by the caller is evidence and is therefore hashed rather than silently sorted.
    """

    if not dataset_id.strip() or not schema_version.strip():
        raise ValueError("dataset_id and schema_version are required")
    if not ordered_rows:
        raise ValueError("cannot fingerprint an empty match population")

    identities: list[dict[str, object]] = []
    seen: set[str] = set()
    prior_event_time: str | None = None
    for index, row in enumerate(ordered_rows):
        match_id = str(row.get("match_id", "")).strip()
        event_time = str(row.get("event_time", "")).strip()
        if not match_id or not event_time:
            raise ValueError(f"row {index} requires match_id and event_time")
        if match_id in seen:
            raise ValueError(f"duplicate match_id in dataset fingerprint: {match_id}")
        if prior_event_time is not None and event_time < prior_event_time:
            raise ValueError("dataset rows must be in non-decreasing event-time order")
        seen.add(match_id)
        prior_event_time = event_time
        identities.append(
            {
                "match_id": match_id,
                "event_time": event_time,
                "player_a_id": str(row.get("player_a_id", "")),
                "player_b_id": str(row.get("player_b_id", "")),
                "tour": str(row.get("tour", "")),
            }
        )

    row_identity_sha256 = _sha256(
        {
            "kind": "tennis-workbench-row-identities-v1",
            "rows": identities,
        }
    )
    payload = {
        "kind": "tennis-workbench-dataset-v1",
        "dataset_id": dataset_id,
        "row_count": len(identities),
        "first_event_time": identities[0]["event_time"],
        "last_event_time": identities[-1]["event_time"],
        "row_identity_sha256": row_identity_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "availability_contract_sha256": availability_contract_sha256,
        "schema_version": schema_version,
    }
    return DatasetFingerprint(**payload, sha256=_sha256(payload))


class CodeFingerprint(WorkbenchRecord):
    """Identity for exact computational components used by one canonical evaluation."""

    components: tuple[tuple[str, str], ...]
    sha256: str

    @field_validator("components")
    @classmethod
    def _validate_components(
        cls,
        value: tuple[tuple[str, str], ...],
    ) -> tuple[tuple[str, str], ...]:
        if not value:
            raise ValueError("code fingerprint requires at least one component")
        names = [name for name, _ in value]
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError("code fingerprint components must be uniquely sorted by name")
        for name, digest in value:
            if not name.strip():
                raise ValueError("code component names must be nonblank")
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("code component digests must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _verify_digest(self) -> "CodeFingerprint":
        expected = _sha256(
            {
                "kind": "tennis-workbench-code-v1",
                "components": {name: digest for name, digest in self.components},
            }
        )
        if self.sha256 != expected:
            raise ValueError("code fingerprint digest does not reproduce")
        return self


def fingerprint_code_components(components: Mapping[str, bytes]) -> CodeFingerprint:
    if not components:
        raise ValueError("cannot fingerprint an empty code component set")
    digests: list[tuple[str, str]] = []
    for name, content in sorted(components.items()):
        if not name.strip():
            raise ValueError("code component names must be nonblank")
        digests.append((name, hashlib.sha256(content).hexdigest()))
    payload = {
        "kind": "tennis-workbench-code-v1",
        "components": {name: digest for name, digest in digests},
    }
    return CodeFingerprint(components=tuple(digests), sha256=_sha256(payload))


class ProcedureSearchFamily(WorkbenchRecord):
    """Frozen declaration of the complete procedure-search attempt universe."""

    family_id: str
    research_question: str
    procedure_ids: tuple[str, ...]
    datasets_touched: tuple[str, ...]
    unregistered_variant_count: int = 0
    parameter_search_count: int = 0
    feature_versions: tuple[str, ...] = ()
    search_method: str
    frozen: bool = False

    @field_validator(
        "procedure_ids",
        "datasets_touched",
        "feature_versions",
    )
    @classmethod
    def _validate_unique_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("search-family tuple fields must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("search-family tuple fields must be nonblank")
        return value

    @model_validator(mode="after")
    def _validate_family(self) -> "ProcedureSearchFamily":
        if not self.family_id.strip() or not self.research_question.strip():
            raise ValueError("family_id and research_question are required")
        if not self.procedure_ids:
            raise ValueError("search family must register at least one procedure")
        if not self.datasets_touched:
            raise ValueError("search family must identify datasets_touched")
        if not self.search_method.strip():
            raise ValueError("search_method is required")
        if self.unregistered_variant_count < 0 or self.parameter_search_count < 0:
            raise ValueError("search-family attempt counts cannot be negative")
        return self

    @property
    def total_trials(self) -> int:
        return (
            len(self.procedure_ids)
            + self.unregistered_variant_count
            + self.parameter_search_count
        )

    def assert_canonical_claim_allowed(self, result_procedure_ids: Sequence[str]) -> None:
        if not self.frozen:
            raise ValueError("canonical adjusted claims require a frozen search family")
        observed = tuple(sorted(set(result_procedure_ids)))
        registered = tuple(sorted(self.procedure_ids))
        if observed != registered:
            raise ValueError(
                "canonical family claim requires results for every registered procedure"
            )


class CanonicalEvaluationBinding(WorkbenchRecord):
    """Identity binding required before a Workbench result becomes canonical evidence."""

    procedure_spec_sha256: str
    evaluation_spec_sha256: str
    dataset_fingerprint_sha256: str
    code_fingerprint_sha256: str
    runtime_id: str
    exposure_graph_sha256: str
    search_family_sha256: str
    evaluation_identity_sha256: str

    @field_validator(
        "procedure_spec_sha256",
        "evaluation_spec_sha256",
        "dataset_fingerprint_sha256",
        "code_fingerprint_sha256",
        "exposure_graph_sha256",
        "search_family_sha256",
        "evaluation_identity_sha256",
    )
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("canonical binding digests must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _verify_identity(self) -> "CanonicalEvaluationBinding":
        expected = _sha256(
            {
                "kind": "tennis-workbench-canonical-evaluation-v1",
                "procedure_spec_sha256": self.procedure_spec_sha256,
                "evaluation_spec_sha256": self.evaluation_spec_sha256,
                "dataset_fingerprint_sha256": self.dataset_fingerprint_sha256,
                "code_fingerprint_sha256": self.code_fingerprint_sha256,
                "runtime_id": self.runtime_id,
                "exposure_graph_sha256": self.exposure_graph_sha256,
                "search_family_sha256": self.search_family_sha256,
            }
        )
        if self.evaluation_identity_sha256 != expected:
            raise ValueError("canonical evaluation identity does not reproduce")
        return self


def build_canonical_evaluation_binding(
    *,
    procedure_spec: ForecastingProcedureSpec,
    evaluation_spec: EvaluationSpec,
    dataset: DatasetFingerprint,
    code: CodeFingerprint,
    exposure_graph_sha256: str,
    search_family: ProcedureSearchFamily,
) -> CanonicalEvaluationBinding:
    if procedure_spec.procedure_id not in evaluation_spec.procedure_ids:
        raise ValueError("procedure is not registered in evaluation")
    if procedure_spec.procedure_id not in search_family.procedure_ids:
        raise ValueError("procedure is not registered in search family")
    if evaluation_spec.population_sha256 != dataset.row_identity_sha256:
        raise ValueError("evaluation population does not match dataset fingerprint")
    if procedure_spec.runtime_id.strip() == "":
        raise ValueError("procedure runtime_id is required")
    payload = {
        "kind": "tennis-workbench-canonical-evaluation-v1",
        "procedure_spec_sha256": procedure_spec.semantic_sha256,
        "evaluation_spec_sha256": evaluation_spec.semantic_sha256,
        "dataset_fingerprint_sha256": dataset.sha256,
        "code_fingerprint_sha256": code.sha256,
        "runtime_id": procedure_spec.runtime_id,
        "exposure_graph_sha256": exposure_graph_sha256,
        "search_family_sha256": search_family.semantic_sha256,
    }
    return CanonicalEvaluationBinding(
        procedure_spec_sha256=procedure_spec.semantic_sha256,
        evaluation_spec_sha256=evaluation_spec.semantic_sha256,
        dataset_fingerprint_sha256=dataset.sha256,
        code_fingerprint_sha256=code.sha256,
        runtime_id=procedure_spec.runtime_id,
        exposure_graph_sha256=exposure_graph_sha256,
        search_family_sha256=search_family.semantic_sha256,
        evaluation_identity_sha256=_sha256(payload),
    )
