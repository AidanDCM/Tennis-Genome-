from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.experiments.pattern_discovery import (
    _bh_adjust,
    _bin_mask,
    build_residual_ledger,
    generate_candidate_specs,
    run_pattern_discovery,
)


def _prediction(match_id: str, year: int, outcome: bool, offset: float) -> dict[str, object]:
    market = 0.42 + offset
    core = 0.46 + offset / 2
    market_core = 0.44 + offset / 3
    return {
        "match_id": match_id,
        "tour": "ATP" if match_id.startswith("atp") else "WTA",
        "year": year,
        "outcome_a": outcome,
        "market_probability_a": market,
        "core_probability_a": core,
        "market_core_probability_a": market_core,
    }


def _results(rows_by_tour: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    claims: list[dict[str, object]] = []
    for tour in ("ATP", "WTA"):
        for signal in ("profile_gap", "genome"):
            claims.append(
                {
                    "tour": tour,
                    "signal_name": signal,
                    "primary": {"predictions": [dict(row) for row in rows_by_tour[tour]]},
                }
            )
    return {
        "stage": "OUTCOME_OPEN_COMPLETE",
        "outcome_open": True,
        "bundle_sha256": "test-bundle",
        "stage_a_seal_sha256": "test-seal",
        "outcomes_sha256": "test-outcomes",
        "market_edge_adv_001": {"family_report": {"claims": claims}},
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _projection(path: Path, *, tour: str, signal_name: str, rows: list[dict[str, object]]) -> None:
    if signal_name == "profile_gap":
        signal_field = "profile_gap_match"
        core_field = "strict_core_probability"
    elif tour == "ATP":
        signal_field = "full_neighbor_residual"
        core_field = "core_probability_a"
    else:
        signal_field = "core_neighbor_residual"
        core_field = "core_probability_a"
    payload = {
        "projection_version": "market-signal-projection-v2",
        "tour": tour,
        "signal_name": signal_name,
        "signal_field": signal_field,
        "core_probability_field": core_field,
        "predictions": [
            {
                "match_id": row["match_id"],
                signal_field: (index - len(rows) / 2) / 100,
                core_field: row["core_probability_a"],
            }
            for index, row in enumerate(rows)
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_residual_ledger_fails_if_frozen_baselines_disagree() -> None:
    rows = {
        "ATP": [_prediction("atp:m1", 2021, True, 0.01)],
        "WTA": [_prediction("wta:m1", 2021, False, -0.01)],
    }
    payload = _results(rows)
    claims = payload["market_edge_adv_001"]["family_report"]["claims"]
    claims[1]["primary"]["predictions"][0] = dict(claims[1]["primary"]["predictions"][0])
    claims[1]["primary"]["predictions"][0]["market_core_probability_a"] = 0.6
    with pytest.raises(ValueError, match="baselines differ"):
        build_residual_ledger(payload)


def test_bh_adjust_is_monotone_and_family_scoped() -> None:
    adjusted = _bh_adjust([("a", 0.01), ("b", 0.02), ("c", 0.2)])
    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["b"] == pytest.approx(0.03)
    assert adjusted["c"] == pytest.approx(0.2)


def test_candidate_generator_is_deterministic_and_uses_discovery_cutpoints() -> None:
    rows = []
    for index in range(30):
        rows.append(
            {
                "year": 2020 + (index % 6),
                "market_probability_a": 0.2 + index / 100,
                "core_probability_a": 0.25 + index / 100,
                "market_core_probability_a": 0.23 + index / 100,
                "market_core_disagreement": 0.05,
                "abs_market_core_disagreement": 0.05,
                "market_confidence": 0.2,
                "market_core_confidence": 0.2,
                "rank_diff": float(index),
                "abs_rank_diff": float(index),
                "rank_points_diff": float(index * 10),
                "abs_rank_points_diff": float(index * 10),
                "age_diff": float(index) / 10,
                "abs_age_diff": float(index) / 10,
                "height_diff": float(index),
                "abs_height_diff": float(index),
                "profile_gap": float(index) / 100,
                "abs_profile_gap": float(index) / 100,
                "genome_signal": float(index) / 200,
                "abs_genome_signal": float(index) / 200,
                "surface": "Hard" if index % 2 else "Clay",
                "tournament_level": "A",
                "round": "R32",
                "best_of": "3",
            }
        )
    frame = pd.DataFrame(rows)
    first = generate_candidate_specs(frame, tour="ATP")
    second = generate_candidate_specs(frame, tour="ATP")
    assert first == second
    assert first
    rank_candidates = [
        item
        for item in first
        if item.definition.get("feature") == "rank_diff" and item.family == "single_variable"
    ]
    assert rank_candidates
    discovery_max = frame.loc[frame["year"] <= 2022, "rank_diff"].max()
    assert max(rank_candidates[0].definition["edges"]) <= discovery_max


def test_full_discovery_artifact_is_self_hashed_and_exploratory(tmp_path: Path) -> None:
    rows_by_tour: dict[str, list[dict[str, object]]] = {"ATP": [], "WTA": []}
    pre_rows: list[dict[str, object]] = []
    for tour in ("ATP", "WTA"):
        for index in range(36):
            year = 2020 + (index % 6)
            match_id = f"{tour.lower()}:m{index}"
            row = _prediction(match_id, year, index % 2 == 0, (index % 10) / 1000)
            rows_by_tour[tour].append(row)
            pre_rows.append(
                {
                    "match_id": match_id,
                    "tour": tour,
                    "event_date": f"{year}-01-01",
                    "surface": "Hard" if index % 2 else "Clay",
                    "tournament_level": "A",
                    "round": "R32",
                    "best_of": 3,
                    "rank_a": 10 + index,
                    "rank_b": 20 + index,
                    "rank_points_a": 2000 - index,
                    "rank_points_b": 1500 - index,
                    "age_years_a": 24.0 + index / 100,
                    "age_years_b": 26.0 + index / 100,
                    "height_cm_a": 185,
                    "height_cm_b": 188,
                }
            )

    results = tmp_path / "results.json"
    results.write_text(json.dumps(_results(rows_by_tour)), encoding="utf-8")
    pre_match = tmp_path / "pre_match.parquet"
    pd.DataFrame(pre_rows).to_parquet(pre_match, index=False)

    paths: dict[str, Path] = {}
    for tour in ("ATP", "WTA"):
        for signal in ("profile_gap", "genome"):
            name = f"{signal}_{tour.lower()}"
            path = tmp_path / f"{name}.json"
            _projection(path, tour=tour, signal_name=signal, rows=rows_by_tour[tour])
            paths[name] = path

    expected = {
        "results": _sha(results),
        "pre_match": _sha(pre_match),
        "profile_gap_atp": _sha(paths["profile_gap_atp"]),
        "profile_gap_wta": _sha(paths["profile_gap_wta"]),
        "genome_atp": _sha(paths["genome_atp"]),
        "genome_wta": _sha(paths["genome_wta"]),
    }
    artifact, residual_rows, feature_rows = run_pattern_discovery(
        results=results,
        pre_match=pre_match,
        profile_gap_atp=paths["profile_gap_atp"],
        profile_gap_wta=paths["profile_gap_wta"],
        genome_atp=paths["genome_atp"],
        genome_wta=paths["genome_wta"],
        expected_hashes=expected,
        enforce_internal_provenance=False,
    )
    assert artifact["experiment_id"] == "PATTERN-DISCOVERY-001"
    assert artifact["exploratory_only"] is True
    assert artifact["production_promotion_allowed"] is False
    assert len(residual_rows) == 72
    assert len(feature_rows) == 72
    unsigned = dict(artifact)
    digest = unsigned.pop("artifact_sha256")
    encoded = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == digest
    assert all("survivor" in item for item in artifact["candidates"])


def test_bin_mask_captures_out_of_discovery_range_values() -> None:
    values = pd.Series([-10.0, 0.5, 1.5, 10.0, float("nan")])
    edges = [0.0, 1.0, 2.0]
    assert _bin_mask(values, edges, 0).tolist() == [True, True, False, False, False]
    assert _bin_mask(values, edges, 1).tolist() == [False, False, True, True, False]
    one_bin = [0.0, 1.0]
    assert _bin_mask(values, one_bin, 0).tolist() == [True, True, True, True, False]
