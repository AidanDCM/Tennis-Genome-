from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.experiments.market_validation_decision import build_validation_decision_artifact


_LABELS = (
    ("ATP", "profile_gap"),
    ("WTA", "profile_gap"),
    ("ATP", "genome"),
    ("WTA", "genome"),
)


def _primary_claim(tour: str, signal: str) -> dict[str, object]:
    return {
        "tour": tour,
        "signal_name": signal,
        "predictions": [
            {
                "outcome_a": False,
                "market_probability_a": 0.45,
                "control_probability_a": 0.47,
                "challenger_probability_a": 0.44,
            },
            {
                "outcome_a": True,
                "market_probability_a": 0.55,
                "control_probability_a": 0.53,
                "challenger_probability_a": 0.56,
            },
        ],
    }


def _adversarial_claim(tour: str, signal: str) -> dict[str, object]:
    return {
        "tour": tour,
        "signal_name": signal,
        "primary": {
            "predictions": [
                {
                    "outcome_a": False,
                    "market_probability_a": 0.45,
                    "core_probability_a": 0.48,
                    "market_only_probability_a": 0.47,
                    "market_core_probability_a": 0.46,
                    "challenger_probability_a": 0.43,
                },
                {
                    "outcome_a": True,
                    "market_probability_a": 0.55,
                    "core_probability_a": 0.52,
                    "market_only_probability_a": 0.53,
                    "market_core_probability_a": 0.54,
                    "challenger_probability_a": 0.57,
                },
            ]
        },
    }


def _bundle() -> dict[str, object]:
    primary_pass = {
        "ATP:profile_gap": True,
        "WTA:profile_gap": True,
        "ATP:genome": False,
        "WTA:genome": True,
    }
    adversarial_pass = {
        "ATP:profile_gap": True,
        "WTA:profile_gap": False,
        "ATP:genome": True,
        "WTA:genome": True,
    }
    return {
        "experiment_id": "MARKET-VALIDATION-BOOK-RUN-001",
        "outcome_open": True,
        "market_edge_001": {
            "family_report": {
                "claims": [_primary_claim(tour, signal) for tour, signal in _LABELS],
                "decisions": [
                    {
                        "label": f"{tour}:{signal}",
                        "market_incremental_pass": primary_pass[f"{tour}:{signal}"],
                    }
                    for tour, signal in _LABELS
                ],
            }
        },
        "market_edge_adv_001": {
            "family_report": {
                "claims": [_adversarial_claim(tour, signal) for tour, signal in _LABELS],
                "decisions": [
                    {
                        "label": f"{tour}:{signal}",
                        "market_core_incremental_pass": adversarial_pass[f"{tour}:{signal}"],
                    }
                    for tour, signal in _LABELS
                ],
            }
        },
    }


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "results.json"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_combined_decision_requires_both_frozen_market_tests(tmp_path: Path) -> None:
    artifact = build_validation_decision_artifact(_write(tmp_path, _bundle()))
    decisions = {row["label"]: row for row in artifact["decisions"]}  # type: ignore[index]

    assert decisions["ATP:profile_gap"]["stack_promotion_pass"] is True
    assert decisions["WTA:profile_gap"]["stack_promotion_pass"] is False
    assert decisions["ATP:genome"]["stack_promotion_pass"] is False
    assert decisions["WTA:genome"]["stack_promotion_pass"] is True
    assert len(str(artifact["artifact_sha256"])) == 64


def test_combined_decision_emits_all_fixed_reliability_views(tmp_path: Path) -> None:
    artifact = build_validation_decision_artifact(_write(tmp_path, _bundle()))
    diagnostics = artifact["diagnostics"]  # type: ignore[index]
    atp = diagnostics["ATP:profile_gap"]  # type: ignore[index]

    assert set(atp["market_edge_001"]) == {
        "market_probability_a",
        "control_probability_a",
        "challenger_probability_a",
    }
    assert set(atp["market_edge_adv_001"]) == {
        "market_probability_a",
        "core_probability_a",
        "market_only_probability_a",
        "market_core_probability_a",
        "challenger_probability_a",
    }
    assert all(
        bucket["n"] > 0
        for buckets in atp["market_edge_adv_001"].values()
        for bucket in buckets
    )


def test_combined_decision_fails_closed_on_missing_claim(tmp_path: Path) -> None:
    payload = _bundle()
    family = payload["market_edge_001"]["family_report"]  # type: ignore[index]
    family["claims"] = family["claims"][:-1]  # type: ignore[index]
    with pytest.raises(ValueError, match="four-claim"):
        build_validation_decision_artifact(_write(tmp_path, payload))
