from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import field_validator, model_validator

from .constitution import ResearchConstitution
from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord
from .exposure import ExposureGraph


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


def _validate_sha256_text(value: str, *, label: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{label} must be lowercase SHA-256")
    return value


def _parse_utc(value: str, *, label: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return parsed.astimezone(UTC)


def _parse_date(value: str, *, label: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD") from exc


class ChronologySemantics(StrEnum):
    """Ordering evidence actually present in the dataset."""

    EXACT_EVENT_TIME = "EXACT_EVENT_TIME"
    EVENT_DATE_MATCH_ID = "EVENT_DATE_MATCH_ID"


class DatasetFingerprint(WorkbenchRecord):
    """Fail-closed identity for one ordered tennis evaluation population.

    A fingerprint preserves the chronology precision the source truly carries.
    Date-only history is fingerprinted as date plus canonical match ID rather than
    being assigned an invented midnight timestamp.
    """

    dataset_id: str
    row_count: int
    chronology_semantics: ChronologySemantics
    first_order_key: str
    last_order_key: str
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
        return _validate_sha256_text(value, label="fingerprint digest")

    @model_validator(mode="after")
    def _verify_digest(self) -> DatasetFingerprint:
        if self.row_count <= 0:
            raise ValueError("dataset fingerprint requires at least one row")
        if not self.first_order_key or not self.last_order_key:
            raise ValueError("dataset fingerprint chronology keys must be nonblank")
        if self.last_order_key < self.first_order_key:
            raise ValueError("dataset fingerprint chronology bounds are reversed")
        expected = _sha256(
            {
                "kind": "tennis-workbench-dataset-v2",
                "dataset_id": self.dataset_id,
                "row_count": self.row_count,
                "chronology_semantics": self.chronology_semantics.value,
                "first_order_key": self.first_order_key,
                "last_order_key": self.last_order_key,
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
    chronology_semantics: ChronologySemantics = ChronologySemantics.EXACT_EVENT_TIME,
) -> DatasetFingerprint:
    """Fingerprint an exact ordered match population without manufacturing chronology.

    EXACT_EVENT_TIME requires a timezone-aware event_time on every row.

    EVENT_DATE_MATCH_ID requires only event_date and uses canonical
    (event_date, match_id) ordering. This is the appropriate mode for the current
    historical research source, where intraday match chronology is not trusted.
    """

    if not dataset_id.strip() or not schema_version.strip():
        raise ValueError("dataset_id and schema_version are required")
    _validate_sha256_text(source_manifest_sha256, label="source_manifest_sha256")
    _validate_sha256_text(
        availability_contract_sha256,
        label="availability_contract_sha256",
    )
    if not ordered_rows:
        raise ValueError("cannot fingerprint an empty match population")

    identities: list[dict[str, object]] = []
    seen: set[str] = set()
    prior_order: tuple[object, ...] | None = None

    for index, row in enumerate(ordered_rows):
        match_id = str(row.get("match_id", "")).strip()
        if not match_id:
            raise ValueError(f"row {index} requires match_id")
        if match_id in seen:
            raise ValueError(f"duplicate match_id in dataset fingerprint: {match_id}")
        seen.add(match_id)

        if chronology_semantics == ChronologySemantics.EXACT_EVENT_TIME:
            event_time_text = str(row.get("event_time", "")).strip()
            if not event_time_text:
                raise ValueError(
                    f"row {index} requires event_time under EXACT_EVENT_TIME chronology"
                )
            event_time = _parse_utc(event_time_text, label=f"row {index} event_time")
            canonical_chronology = event_time.isoformat()
            order = (event_time,)
        elif chronology_semantics == ChronologySemantics.EVENT_DATE_MATCH_ID:
            event_date_text = str(row.get("event_date", "")).strip()
            if not event_date_text:
                raise ValueError(
                    f"row {index} requires event_date under EVENT_DATE_MATCH_ID chronology"
                )
            event_date = _parse_date(event_date_text, label=f"row {index} event_date")
            canonical_chronology = event_date.isoformat()
            order = (event_date, match_id)
        else:
            raise AssertionError(f"unsupported chronology semantics: {chronology_semantics}")

        if prior_order is not None and order < prior_order:
            raise ValueError(
                "dataset rows must be in non-decreasing order under registered chronology"
            )
        prior_order = order

        identities.append(
            {
                "match_id": match_id,
                "chronology": canonical_chronology,
                "player_a_id": str(row.get("player_a_id", "")),
                "player_b_id": str(row.get("player_b_id", "")),
                "tour": str(row.get("tour", "")),
            }
        )

    row_identity_sha256 = _sha256(
        {
            "kind": "tennis-workbench-row-identities-v2",
            "chronology_semantics": chronology_semantics.value,
            "rows": identities,
        }
    )
    first = identities[0]
    last = identities[-1]
    first_order_key = f"{first['chronology']}|{first['match_id']}"
    last_order_key = f"{last['chronology']}|{last['match_id']}"
    fields = {
        "dataset_id": dataset_id,
        "row_count": len(identities),
        "chronology_semantics": chronology_semantics,
        "first_order_key": first_order_key,
        "last_order_key": last_order_key,
        "row_identity_sha256": row_identity_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "availability_contract_sha256": availability_contract_sha256,
        "schema_version": schema_version,
    }
    digest_payload = {
        "kind": "tennis-workbench-dataset-v2",
        **{
            **fields,
            "chronology_semantics": chronology_semantics.value,
        },
    }
    return DatasetFingerprint(**fields, sha256=_sha256(digest_payload))


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
            _validate_sha256_text(digest, label="code component digest")
        return value

    @model_validator(mode="after")
    def _verify_digest(self) -> CodeFingerprint:
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
    def _validate_family(self) -> ProcedureSearchFamily:
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
    constitution_sha256: str
    evaluation_identity_sha256: str

    @field_validator(
        "procedure_spec_sha256",
        "evaluation_spec_sha256",
        "dataset_fingerprint_sha256",
        "code_fingerprint_sha256",
        "exposure_graph_sha256",
        "search_family_sha256",
        "constitution_sha256",
        "evaluation_identity_sha256",
    )
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _validate_sha256_text(value, label="canonical binding digest")

    @model_validator(mode="after")
    def _verify_identity(self) -> CanonicalEvaluationBinding:
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
                "constitution_sha256": self.constitution_sha256,
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
    exposure_graph: ExposureGraph,
    search_family: ProcedureSearchFamily,
    constitution: ResearchConstitution,
) -> CanonicalEvaluationBinding:
    if procedure_spec.procedure_id not in evaluation_spec.procedure_ids:
        raise ValueError("procedure is not registered in evaluation")
    if procedure_spec.procedure_id not in search_family.procedure_ids:
        raise ValueError("procedure is not registered in search family")
    if evaluation_spec.population_sha256 != dataset.row_identity_sha256:
        raise ValueError("evaluation population does not match dataset fingerprint")
    if dataset.dataset_id not in search_family.datasets_touched:
        raise ValueError("dataset fingerprint is not declared in search family")
    if not search_family.frozen:
        raise ValueError("canonical evaluation requires a frozen search family")
    exposure_graph.assert_registered(procedure_spec.development_exposure_ids)
    payload = {
        "kind": "tennis-workbench-canonical-evaluation-v1",
        "procedure_spec_sha256": procedure_spec.semantic_sha256,
        "evaluation_spec_sha256": evaluation_spec.semantic_sha256,
        "dataset_fingerprint_sha256": dataset.sha256,
        "code_fingerprint_sha256": code.sha256,
        "runtime_id": procedure_spec.runtime_id,
        "exposure_graph_sha256": exposure_graph.semantic_sha256,
        "search_family_sha256": search_family.semantic_sha256,
        "constitution_sha256": constitution.semantic_sha256,
    }
    return CanonicalEvaluationBinding(
        procedure_spec_sha256=procedure_spec.semantic_sha256,
        evaluation_spec_sha256=evaluation_spec.semantic_sha256,
        dataset_fingerprint_sha256=dataset.sha256,
        code_fingerprint_sha256=code.sha256,
        runtime_id=procedure_spec.runtime_id,
        exposure_graph_sha256=exposure_graph.semantic_sha256,
        search_family_sha256=search_family.semantic_sha256,
        constitution_sha256=constitution.semantic_sha256,
        evaluation_identity_sha256=_sha256(payload),
    )
