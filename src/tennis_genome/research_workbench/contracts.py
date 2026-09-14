from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_MARKET_TOKENS = (
    "bookmaker",
    "sportsbook",
    "closing_line",
    "implied_probability",
    "market_odds",
    "odds",
    "profit",
    "stake",
    "wager",
    "clv",
)


class WorkbenchRecord(BaseModel):
    """Immutable, canonicalizable research record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def canonical_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    @property
    def semantic_sha256(self) -> str:
        payload = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class ForecastingProcedureSpec(WorkbenchRecord):
    """Complete reproducible definition of one forecasting challenger.

    Pattern/rule discovery is intentionally not the primary object. A procedure must define
    a complete route from legitimate pre-match inputs to probabilities.
    """

    procedure_id: str
    name: str
    version: str
    input_contract: str
    feature_set: tuple[str, ...]
    training_method: str
    hyperparameters_json: str = "{}"
    calibration: str
    prediction_method: str
    required_data: tuple[str, ...] = ()
    development_exposure_ids: tuple[str, ...] = ()
    parent_procedure_ids: tuple[str, ...] = ()
    source_code_sha: str
    runtime_id: str
    random_seed: int | None = None
    market_blind: Literal[True] = True

    @field_validator("hyperparameters_json")
    @classmethod
    def _canonicalize_hyperparameters(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("hyperparameters_json must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("hyperparameters_json must encode a JSON object")
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @field_validator("feature_set", "required_data", "development_exposure_ids", "parent_procedure_ids")
    @classmethod
    def _require_unique_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("tuple fields must not contain duplicates")
        if any(not item.strip() for item in value):
            raise ValueError("tuple fields must not contain blank values")
        return value

    @model_validator(mode="after")
    def _enforce_independent_probability_boundary(self) -> Self:
        searchable = " ".join((self.input_contract, *self.feature_set, *self.required_data)).lower()
        forbidden = sorted(token for token in _FORBIDDEN_MARKET_TOKENS if token in searchable)
        if forbidden:
            raise ValueError(
                "independent research procedures may not consume downstream market semantics: "
                + ", ".join(forbidden)
            )
        return self


class EvaluationSpec(WorkbenchRecord):
    """Frozen definition of a comparison among complete forecasting procedures."""

    evaluation_id: str
    dataset_version: str
    population_sha256: str
    procedure_ids: tuple[str, ...]
    evaluation_role: Literal["DEVELOPMENT", "PROTECTED"]
    primary_metrics: tuple[Literal["brier", "log_loss"], ...] = ("brier", "log_loss")
    outcome_access_policy: Literal["OUTCOMES_VISIBLE", "SEALED_UNTIL_EVALUATION"]

    @field_validator("population_sha256")
    @classmethod
    def _validate_population_sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("population_sha256 must be a lowercase 64-character SHA-256")
        return value

    @field_validator("procedure_ids")
    @classmethod
    def _validate_procedure_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one procedure is required")
        if len(set(value)) != len(value):
            raise ValueError("procedure_ids must be unique")
        return value

    @model_validator(mode="after")
    def _enforce_protected_outcome_policy(self) -> Self:
        if self.evaluation_role == "PROTECTED" and self.outcome_access_policy != "SEALED_UNTIL_EVALUATION":
            raise ValueError("protected evaluations must seal outcomes until evaluation")
        return self
