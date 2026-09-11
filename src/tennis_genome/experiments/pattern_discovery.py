from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp

from tennis_genome.evaluation.metrics import brier_score, binary_log_loss, calibration_bins

_EXPERIMENT_ID = "PATTERN-DISCOVERY-001"
_VERSION = "pattern-discovery-v1"
_DISCOVERY_END_YEAR = 2022
_VALIDATION_YEARS = (2023, 2024, 2025)
_BOOTSTRAP_RESAMPLES = 2_000
_BOOTSTRAP_SEED_NAMESPACE = 1729
_MIN_DISCOVERY_N = 500
_MIN_VALIDATION_N = 300
_FDR_ALPHA = 0.10

_EXPECTED_HASHES = {
    "results": "6419f5fbfa24ed6399771ce9a8ed23a46aa8720406acf987498eb24ed139e88d",
    "pre_match": "557e579cd69b04b7436fee342d90d44a3a7e982f128b586ca0e6d1e01b0eec9e",
    "profile_gap_atp": "8dc6524e70b593fcbc03cc0af0e5d74675dcdff8777af9c693f3df36d07cc472",
    "profile_gap_wta": "315ae83acf91b58200a09f91a466f4b4ef19b03848175afce3fa86b0be1ce795",
    "genome_atp": "4e83ffb4f751d901934a4124d215e4dee9ef9eacd9f5c2b9590fd86334e6965b",
    "genome_wta": "2bc89fbfae1a4ba281fe2f859fb6a72a2ad9fd9702d4a0c172ad3962a50e239f",
}
_EXPECTED_BUNDLE_SHA = "be097af8ff9052a1484bdc25fab861d75ada78e21252c7bdb9cfde42ab093a54"
_EXPECTED_STAGE_A_SHA = "b9260e9ab398dc10bdf358e99d5ca26f61ba3ef0970eca1abc48568ed0508b84"
_EXPECTED_OUTCOMES_SHA = "c509dff1bbe4b1e10944f5b361138790f85ccdb21b7d12aafb03ddc0b1e8c63d"

Tour = Literal["ATP", "WTA"]
Family = Literal["single_variable", "pairwise_context", "uncertainty_ood"]

_NUMERIC_FEATURES = (
    "market_probability_a",
    "core_probability_a",
    "market_core_probability_a",
    "market_core_disagreement",
    "abs_market_core_disagreement",
    "market_confidence",
    "market_core_confidence",
    "rank_diff",
    "abs_rank_diff",
    "rank_points_diff",
    "abs_rank_points_diff",
    "age_diff",
    "abs_age_diff",
    "height_diff",
    "abs_height_diff",
    "profile_gap",
    "abs_profile_gap",
    "genome_signal",
    "abs_genome_signal",
)
_CONTEXT_FEATURES = ("surface", "tournament_level", "round", "best_of")
_MARKET_BANDS = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    tour: Tour
    family: Family
    definition: dict[str, object]
    required_features: tuple[str, ...]


@dataclass(frozen=True)
class BootstrapInterval:
    lower: float | None
    upper: float | None
    seed: int
    n_resamples: int


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _payload_sha(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load_json(path: str | Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _verify_inputs(
    *,
    results: Path,
    pre_match: Path,
    profile_gap_atp: Path,
    profile_gap_wta: Path,
    genome_atp: Path,
    genome_wta: Path,
    expected_hashes: dict[str, str],
    enforce_internal_provenance: bool,
) -> dict[str, str]:
    paths = {
        "results": results,
        "pre_match": pre_match,
        "profile_gap_atp": profile_gap_atp,
        "profile_gap_wta": profile_gap_wta,
        "genome_atp": genome_atp,
        "genome_wta": genome_wta,
    }
    if set(paths) != set(expected_hashes):
        raise ValueError("expected hash keys differ from discovery input set")
    observed: dict[str, str] = {}
    for name, path in paths.items():
        digest = _sha256_file(path)
        observed[name] = digest
        if digest != expected_hashes[name]:
            raise ValueError(
                f"PATTERN-DISCOVERY frozen input hash mismatch for {name}: "
                f"expected {expected_hashes[name]}, got {digest}"
            )

    if enforce_internal_provenance:
        payload = _load_json(results)
        if payload.get("bundle_sha256") != _EXPECTED_BUNDLE_SHA:
            raise ValueError("confirmatory validation bundle SHA differs from frozen discovery source")
        if payload.get("stage_a_seal_sha256") != _EXPECTED_STAGE_A_SHA:
            raise ValueError("Stage-A seal SHA differs from frozen discovery source")
        if payload.get("outcomes_sha256") != _EXPECTED_OUTCOMES_SHA:
            raise ValueError("outcomes SHA differs from frozen discovery source")
        if payload.get("stage") != "OUTCOME_OPEN_COMPLETE" or payload.get("outcome_open") is not True:
            raise ValueError("confirmatory source is not a completed outcome-open bundle")
    return observed


def _claims_by_tour(results_payload: dict[str, object]) -> dict[Tour, dict[str, dict[str, object]]]:
    adv = results_payload.get("market_edge_adv_001")
    if not isinstance(adv, dict):
        raise ValueError("confirmatory results lack MARKET-EDGE-ADV-001")
    family = adv.get("family_report")
    if not isinstance(family, dict):
        raise ValueError("adversarial artifact lacks family_report")
    claims = family.get("claims")
    if not isinstance(claims, list):
        raise ValueError("adversarial family report lacks claims")
    result: dict[Tour, dict[str, dict[str, object]]] = {"ATP": {}, "WTA": {}}
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("invalid adversarial claim")
        tour = str(claim.get("tour"))
        signal = str(claim.get("signal_name"))
        if tour not in result or signal not in {"profile_gap", "genome"}:
            raise ValueError("unexpected adversarial claim label")
        result[tour][signal] = claim
    if any(set(claims_by_signal) != {"profile_gap", "genome"} for claims_by_signal in result.values()):
        raise ValueError("expected ATP/WTA × Profile Gap/Genome adversarial claims")
    return result


def _prediction_map(claim: dict[str, object]) -> dict[str, tuple[object, ...]]:
    primary = claim.get("primary")
    if not isinstance(primary, dict) or not isinstance(primary.get("predictions"), list):
        raise ValueError("adversarial claim lacks primary predictions")
    result: dict[str, tuple[object, ...]] = {}
    for raw in primary["predictions"]:
        if not isinstance(raw, dict):
            raise ValueError("invalid adversarial prediction row")
        match_id = str(raw.get("match_id", ""))
        if not match_id or match_id in result:
            raise ValueError("empty or duplicate adversarial prediction match_id")
        result[match_id] = (
            bool(raw["outcome_a"]),
            float(raw["market_probability_a"]),
            float(raw["core_probability_a"]),
            float(raw["market_core_probability_a"]),
            int(raw["year"]),
        )
    return result


def build_residual_ledger(results_payload: dict[str, object]) -> list[dict[str, object]]:
    """Build the canonical Market+Core residual ledger after cross-claim equality checks."""

    claims = _claims_by_tour(results_payload)
    rows: list[dict[str, object]] = []
    for tour in ("ATP", "WTA"):
        profile = _prediction_map(claims[tour]["profile_gap"])
        genome = _prediction_map(claims[tour]["genome"])
        if profile != genome:
            raise ValueError(f"{tour} Profile Gap and Genome Market+Core baselines differ")
        for match_id, values in sorted(profile.items()):
            outcome, market, core, market_core, year = values
            if not 0.0 < market < 1.0 or not 0.0 < core < 1.0 or not 0.0 < market_core < 1.0:
                raise ValueError("residual ledger probabilities must be in (0, 1)")
            rows.append(
                {
                    "match_id": match_id,
                    "tour": tour,
                    "year": year,
                    "outcome_a": outcome,
                    "market_probability_a": market,
                    "core_probability_a": core,
                    "market_core_probability_a": market_core,
                    "residual": (1.0 if outcome else 0.0) - market_core,
                }
            )
    return sorted(rows, key=lambda row: (str(row["tour"]), int(row["year"]), str(row["match_id"])))


def _projection_map(path: Path, *, expected_tour: Tour) -> dict[str, tuple[float, float]]:
    payload = _load_json(path)
    if payload.get("projection_version") != "market-signal-projection-v2":
        raise ValueError("pattern discovery requires market-signal-projection-v2")
    if payload.get("tour") != expected_tour:
        raise ValueError("signal projection tour mismatch")
    signal_field = str(payload.get("signal_field", ""))
    core_field = str(payload.get("core_probability_field", ""))
    predictions = payload.get("predictions")
    if not signal_field or not core_field or not isinstance(predictions, list):
        raise ValueError("invalid signal projection")
    result: dict[str, tuple[float, float]] = {}
    for row in predictions:
        if not isinstance(row, dict):
            raise ValueError("invalid signal projection row")
        match_id = str(row.get("match_id", ""))
        if not match_id or match_id in result:
            raise ValueError("empty or duplicate signal projection match_id")
        signal = float(row[signal_field])
        core = float(row[core_field])
        if not math.isfinite(signal) or not 0.0 < core < 1.0:
            raise ValueError("invalid projected signal/Core value")
        result[match_id] = (signal, core)
    return result


def build_feature_ledger(
    residual_rows: list[dict[str, object]],
    *,
    pre_match: Path,
    projection_paths: dict[Tour, dict[str, Path]],
) -> pd.DataFrame:
    frame = pd.read_parquet(pre_match)
    if "match_id" not in frame.columns:
        raise ValueError("pre_match parquet lacks match_id")
    if frame["match_id"].duplicated().any():
        raise ValueError("pre_match parquet contains duplicate match_id")

    residual = pd.DataFrame(residual_rows)
    frame = residual.merge(frame, on="match_id", how="left", validate="one_to_one", suffixes=("", "_pre"))
    if frame["tour_pre"].isna().any():
        raise ValueError("residual ledger contains matches missing from pre_match parquet")
    if not (frame["tour"] == frame["tour_pre"]).all():
        raise ValueError("tour mismatch between residual and pre_match ledgers")

    for tour in ("ATP", "WTA"):
        profile = _projection_map(projection_paths[tour]["profile_gap"], expected_tour=tour)
        genome = _projection_map(projection_paths[tour]["genome"], expected_tour=tour)
        tour_mask = frame["tour"] == tour
        profile_signal: list[float] = []
        genome_signal: list[float] = []
        for match_id, core in zip(
            frame.loc[tour_mask, "match_id"],
            frame.loc[tour_mask, "core_probability_a"],
            strict=True,
        ):
            if match_id not in profile or match_id not in genome:
                raise ValueError(f"{tour} residual match missing from frozen signal projection")
            p_signal, p_core = profile[match_id]
            g_signal, g_core = genome[match_id]
            if p_core != float(core) or g_core != float(core):
                raise ValueError(f"{tour} projected Core probability differs from confirmatory residual ledger")
            profile_signal.append(p_signal)
            genome_signal.append(g_signal)
        frame.loc[tour_mask, "profile_gap"] = profile_signal
        frame.loc[tour_mask, "genome_signal"] = genome_signal

    numeric_sources = (
        "rank_a",
        "rank_b",
        "rank_points_a",
        "rank_points_b",
        "age_years_a",
        "age_years_b",
        "height_cm_a",
        "height_cm_b",
    )
    for column in numeric_sources:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["market_core_disagreement"] = frame["core_probability_a"] - frame["market_probability_a"]
    frame["abs_market_core_disagreement"] = frame["market_core_disagreement"].abs()
    frame["market_confidence"] = (frame["market_probability_a"] - 0.5).abs()
    frame["market_core_confidence"] = (frame["market_core_probability_a"] - 0.5).abs()
    frame["rank_diff"] = frame["rank_b"] - frame["rank_a"]
    frame["abs_rank_diff"] = frame["rank_diff"].abs()
    frame["rank_points_diff"] = frame["rank_points_a"] - frame["rank_points_b"]
    frame["abs_rank_points_diff"] = frame["rank_points_diff"].abs()
    frame["age_diff"] = frame["age_years_a"] - frame["age_years_b"]
    frame["abs_age_diff"] = frame["age_diff"].abs()
    frame["height_diff"] = frame["height_cm_a"] - frame["height_cm_b"]
    frame["abs_height_diff"] = frame["height_diff"].abs()
    frame["abs_profile_gap"] = frame["profile_gap"].abs()
    frame["abs_genome_signal"] = frame["genome_signal"].abs()
    frame["best_of"] = frame.get("best_of", pd.Series(index=frame.index, dtype="object")).astype("string")
    for column in ("surface", "tournament_level", "round"):
        if column not in frame.columns:
            frame[column] = pd.Series(index=frame.index, dtype="string")
        frame[column] = frame[column].astype("string")
    return frame


def _finite(values: pd.Series) -> np.ndarray:
    array = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    return array[np.isfinite(array)]


def _quantile_edges(values: pd.Series, n_bins: int) -> list[float]:
    finite = _finite(values)
    if len(finite) == 0:
        return []
    edges = np.quantile(finite, np.linspace(0.0, 1.0, n_bins + 1), method="linear")
    result: list[float] = []
    for value in edges.tolist():
        number = float(value)
        if not result or number > result[-1]:
            result.append(number)
    return result if len(result) >= 2 else []


def _bin_mask(values: pd.Series, edges: list[float], index: int) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if index < 0 or index >= len(edges) - 1:
        raise ValueError("invalid bin index")
    lower, upper = edges[index], edges[index + 1]
    if index == len(edges) - 2:
        return numeric.ge(lower) & numeric.le(upper)
    return numeric.ge(lower) & numeric.lt(upper)


def _market_band_mask(values: pd.Series, index: int) -> pd.Series:
    lower, upper = _MARKET_BANDS[index]
    numeric = pd.to_numeric(values, errors="coerce")
    if index == len(_MARKET_BANDS) - 1:
        return numeric.ge(lower) & numeric.le(upper)
    return numeric.ge(lower) & numeric.lt(upper)


def _candidate_id(tour: Tour, family: Family, definition: dict[str, object]) -> str:
    digest = hashlib.sha256(_canonical_bytes(definition)).hexdigest()[:16]
    return f"{tour}:{family}:{digest}"


def _spec(tour: Tour, family: Family, definition: dict[str, object], required: tuple[str, ...]) -> CandidateSpec:
    return CandidateSpec(
        candidate_id=_candidate_id(tour, family, definition),
        tour=tour,
        family=family,
        definition=definition,
        required_features=required,
    )


def generate_candidate_specs(tour_frame: pd.DataFrame, *, tour: Tour) -> list[CandidateSpec]:
    discovery = tour_frame[tour_frame["year"] <= _DISCOVERY_END_YEAR]
    specs: list[CandidateSpec] = []

    for feature in _NUMERIC_FEATURES:
        edges = _quantile_edges(discovery[feature], 5)
        for index in range(max(0, len(edges) - 1)):
            definition = {"kind": "quantile_cell", "feature": feature, "edges": edges, "bin": index}
            specs.append(_spec(tour, "single_variable", definition, (feature,)))

    for feature in _CONTEXT_FEATURES:
        levels = sorted(str(value) for value in discovery[feature].dropna().unique().tolist())
        for level in levels:
            definition = {"kind": "category", "feature": feature, "value": level}
            specs.append(_spec(tour, "single_variable", definition, (feature,)))

    for index, (lower, upper) in enumerate(_MARKET_BANDS):
        definition = {
            "kind": "market_band",
            "feature": "market_probability_a",
            "band": index,
            "lower": lower,
            "upper": upper,
        }
        specs.append(_spec(tour, "single_variable", definition, ("market_probability_a",)))

    pairwise = (
        ("market_core_disagreement", "surface", "surface"),
        ("abs_market_core_disagreement", "market_probability_a", "market_band"),
        ("rank_diff", "surface", "surface"),
        ("profile_gap", "surface", "surface"),
        ("genome_signal", "surface", "surface"),
    )
    for numeric_feature, context_feature, context_kind in pairwise:
        edges = _quantile_edges(discovery[numeric_feature], 3)
        if not edges:
            continue
        if context_kind == "surface":
            context_values: list[object] = sorted(
                str(value) for value in discovery[context_feature].dropna().unique().tolist()
            )
        else:
            context_values = list(range(len(_MARKET_BANDS)))
        for index in range(len(edges) - 1):
            for context_value in context_values:
                definition = {
                    "kind": "pairwise",
                    "numeric_feature": numeric_feature,
                    "edges": edges,
                    "bin": index,
                    "context_feature": context_feature,
                    "context_kind": context_kind,
                    "context_value": context_value,
                }
                specs.append(
                    _spec(
                        tour,
                        "pairwise_context",
                        definition,
                        (numeric_feature, context_feature),
                    )
                )

    for feature in (
        "abs_market_core_disagreement",
        "market_confidence",
        "market_core_confidence",
        "abs_profile_gap",
        "abs_genome_signal",
    ):
        edges = _quantile_edges(discovery[feature], 5)
        for index in range(max(0, len(edges) - 1)):
            definition = {"kind": "quantile_cell", "feature": feature, "edges": edges, "bin": index}
            specs.append(_spec(tour, "uncertainty_ood", definition, (feature,)))

    for feature_a, feature_b in (
        ("abs_market_core_disagreement", "market_core_confidence"),
        ("abs_profile_gap", "abs_genome_signal"),
    ):
        edges_a = _quantile_edges(discovery[feature_a], 3)
        edges_b = _quantile_edges(discovery[feature_b], 3)
        if not edges_a or not edges_b:
            continue
        for index_a in range(len(edges_a) - 1):
            for index_b in range(len(edges_b) - 1):
                definition = {
                    "kind": "two_numeric_bins",
                    "feature_a": feature_a,
                    "edges_a": edges_a,
                    "bin_a": index_a,
                    "feature_b": feature_b,
                    "edges_b": edges_b,
                    "bin_b": index_b,
                }
                specs.append(
                    _spec(
                        tour,
                        "uncertainty_ood",
                        definition,
                        (feature_a, feature_b),
                    )
                )

    by_id = {item.candidate_id: item for item in specs}
    if len(by_id) != len(specs):
        raise ValueError("candidate generator produced duplicate IDs")
    return sorted(specs, key=lambda item: (item.family, item.candidate_id))


def _mask(frame: pd.DataFrame, spec: CandidateSpec) -> pd.Series:
    d = spec.definition
    kind = d["kind"]
    if kind == "quantile_cell":
        return _bin_mask(frame[str(d["feature"])], list(d["edges"]), int(d["bin"]))
    if kind == "category":
        return frame[str(d["feature"])].astype("string").eq(str(d["value"]))
    if kind == "market_band":
        return _market_band_mask(frame["market_probability_a"], int(d["band"]))
    if kind == "pairwise":
        first = _bin_mask(
            frame[str(d["numeric_feature"])],
            list(d["edges"]),
            int(d["bin"]),
        )
        if d["context_kind"] == "surface":
            second = frame[str(d["context_feature"])].astype("string").eq(str(d["context_value"]))
        else:
            second = _market_band_mask(frame["market_probability_a"], int(d["context_value"]))
        return first & second
    if kind == "two_numeric_bins":
        return _bin_mask(frame[str(d["feature_a"])], list(d["edges_a"]), int(d["bin_a"])) & _bin_mask(
            frame[str(d["feature_b"])], list(d["edges_b"]), int(d["bin_b"])
        )
    raise ValueError(f"unknown candidate kind {kind}")


def _seed(spec: CandidateSpec) -> int:
    material = f"{_EXPERIMENT_ID}|{spec.tour}|{spec.family}|{spec.candidate_id}|{_BOOTSTRAP_SEED_NAMESPACE}"
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")


def _bootstrap_mean(values: np.ndarray, *, seed: int) -> BootstrapInterval:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return BootstrapInterval(None, None, seed, _BOOTSTRAP_RESAMPLES)
    rng = np.random.default_rng(seed)
    draws: list[np.ndarray] = []
    remaining = _BOOTSTRAP_RESAMPLES
    chunk_size = 100
    while remaining:
        chunk = min(chunk_size, remaining)
        indices = rng.integers(0, len(finite), size=(chunk, len(finite)))
        draws.append(finite[indices].mean(axis=1))
        remaining -= chunk
    means = np.concatenate(draws)
    lower, upper = np.quantile(means, [0.025, 0.975], method="linear")
    return BootstrapInterval(float(lower), float(upper), seed, _BOOTSTRAP_RESAMPLES)


def _raw_p(residuals: np.ndarray) -> float:
    finite = residuals[np.isfinite(residuals)]
    if len(finite) < 2 or float(np.std(finite, ddof=1)) == 0.0:
        return 1.0
    result = ttest_1samp(finite, popmean=0.0, alternative="two-sided")
    p = float(result.pvalue)
    return p if math.isfinite(p) else 1.0


def _bh_adjust(items: list[tuple[str, float]]) -> dict[str, float]:
    if not items:
        return {}
    ordered = sorted(((label, float(p)) for label, p in items), key=lambda item: (item[1], item[0]))
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank_from_end in range(m, 0, -1):
        label, raw = ordered[rank_from_end - 1]
        value = min(1.0, raw * m / rank_from_end)
        running = min(running, value)
        adjusted[label] = running
    return adjusted


def _market_summary(values: pd.Series) -> dict[str, float | int | None]:
    finite = _finite(values)
    if len(finite) == 0:
        return {"n": 0, "mean": None, "q10": None, "median": None, "q90": None}
    q10, median, q90 = np.quantile(finite, [0.1, 0.5, 0.9], method="linear")
    return {
        "n": int(len(finite)),
        "mean": float(finite.mean()),
        "q10": float(q10),
        "median": float(median),
        "q90": float(q90),
    }


def _metric_diagnostic(frame: pd.DataFrame, correction: float) -> dict[str, object] | None:
    if frame.empty:
        return None
    outcomes = frame["outcome_a"].astype(bool).tolist()
    baseline = frame["market_core_probability_a"].astype(float).to_numpy()
    corrected = np.clip(baseline + correction, 0.001, 0.999)
    bins = [asdict(item) for item in calibration_bins(outcomes, corrected.tolist(), n_bins=10)]
    return {
        "correction": correction,
        "baseline_brier": brier_score(outcomes, baseline.tolist()),
        "corrected_brier": brier_score(outcomes, corrected.tolist()),
        "baseline_log_loss": binary_log_loss(outcomes, baseline.tolist()),
        "corrected_log_loss": binary_log_loss(outcomes, corrected.tolist()),
        "corrected_reliability": bins,
    }


def _sign(value: float) -> int:
    return 1 if value > 0.0 else -1 if value < 0.0 else 0


def _evaluate_candidate(
    frame: pd.DataFrame,
    spec: CandidateSpec,
) -> dict[str, object]:
    discovery_frame = frame[frame["year"] <= _DISCOVERY_END_YEAR]
    validation_frame = frame[frame["year"].isin(_VALIDATION_YEARS)]
    d_mask = _mask(discovery_frame, spec).fillna(False)
    v_mask = _mask(validation_frame, spec).fillna(False)
    d_cell = discovery_frame.loc[d_mask]
    v_cell = validation_frame.loc[v_mask]
    d_residual = _finite(d_cell["residual"])
    v_residual = _finite(v_cell["residual"])
    d_mean = float(d_residual.mean()) if len(d_residual) else 0.0
    v_mean = float(v_residual.mean()) if len(v_residual) else 0.0
    seed = _seed(spec)
    d_ci = _bootstrap_mean(d_residual, seed=seed)
    v_ci = _bootstrap_mean(v_residual, seed=seed ^ 0x9E3779B97F4A7C15)
    contributions = {
        str(year): float(v_cell.loc[v_cell["year"] == year, "residual"].sum())
        for year in _VALIDATION_YEARS
        if not v_cell.loc[v_cell["year"] == year].empty
    }
    abs_total = sum(abs(value) for value in contributions.values())
    concentration = max((abs(value) for value in contributions.values()), default=0.0) / abs_total if abs_total else None
    required_missing_discovery = int(discovery_frame[list(spec.required_features)].isna().any(axis=1).sum())
    required_missing_validation = int(validation_frame[list(spec.required_features)].isna().any(axis=1).sum())
    return {
        "candidate_id": spec.candidate_id,
        "tour": spec.tour,
        "family": spec.family,
        "definition": spec.definition,
        "required_features": list(spec.required_features),
        "discovery_n": int(len(d_residual)),
        "validation_n": int(len(v_residual)),
        "discovery_mean_residual": d_mean,
        "validation_mean_residual": v_mean,
        "raw_discovery_p": _raw_p(d_residual),
        "discovery_bootstrap": asdict(d_ci),
        "validation_bootstrap": asdict(v_ci),
        "same_direction": _sign(d_mean) != 0 and _sign(d_mean) == _sign(v_mean),
        "validation_year_contributions": contributions,
        "validation_years_represented": len(contributions),
        "validation_concentration_ratio": concentration,
        "market_probability_discovery": _market_summary(d_cell["market_probability_a"]),
        "market_probability_validation": _market_summary(v_cell["market_probability_a"]),
        "missingness": {
            "tour_discovery_n": int(len(discovery_frame)),
            "tour_validation_n": int(len(validation_frame)),
            "required_feature_missing_discovery": required_missing_discovery,
            "required_feature_missing_validation": required_missing_validation,
        },
        "validation_probability_diagnostic": _metric_diagnostic(v_cell, d_mean),
    }


def _feature_ledger_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    fields = (
        "match_id",
        "tour",
        "year",
        "market_probability_a",
        "core_probability_a",
        "market_core_probability_a",
        "profile_gap",
        "genome_signal",
        "surface",
        "tournament_level",
        "round",
        "best_of",
        "rank_a",
        "rank_b",
        "rank_points_a",
        "rank_points_b",
        "age_years_a",
        "age_years_b",
        "height_cm_a",
        "height_cm_b",
    )
    rows: list[dict[str, object]] = []
    for raw in frame.loc[:, fields].sort_values(["tour", "year", "match_id"]).to_dict(orient="records"):
        row: dict[str, object] = {}
        for key, value in raw.items():
            if pd.isna(value):
                row[key] = None
            elif isinstance(value, np.generic):
                row[key] = value.item()
            else:
                row[key] = value
        rows.append(row)
    return rows


def run_pattern_discovery(
    *,
    results: Path,
    pre_match: Path,
    profile_gap_atp: Path,
    profile_gap_wta: Path,
    genome_atp: Path,
    genome_wta: Path,
    expected_hashes: dict[str, str] | None = None,
    enforce_internal_provenance: bool = True,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    expected = _EXPECTED_HASHES if expected_hashes is None else expected_hashes
    observed_hashes = _verify_inputs(
        results=results,
        pre_match=pre_match,
        profile_gap_atp=profile_gap_atp,
        profile_gap_wta=profile_gap_wta,
        genome_atp=genome_atp,
        genome_wta=genome_wta,
        expected_hashes=expected,
        enforce_internal_provenance=enforce_internal_provenance,
    )
    results_payload = _load_json(results)
    residual_rows = build_residual_ledger(results_payload)
    residual_ledger_sha = _payload_sha(residual_rows)
    feature_frame = build_feature_ledger(
        residual_rows,
        pre_match=pre_match,
        projection_paths={
            "ATP": {"profile_gap": profile_gap_atp, "genome": genome_atp},
            "WTA": {"profile_gap": profile_gap_wta, "genome": genome_wta},
        },
    )
    feature_rows = _feature_ledger_rows(feature_frame)
    feature_ledger_sha = _payload_sha(feature_rows)

    evaluated: list[dict[str, object]] = []
    specs: list[CandidateSpec] = []
    for tour in ("ATP", "WTA"):
        tour_frame = feature_frame.loc[feature_frame["tour"] == tour].copy()
        tour_specs = generate_candidate_specs(tour_frame, tour=tour)
        specs.extend(tour_specs)
        evaluated.extend(_evaluate_candidate(tour_frame, item) for item in tour_specs)

    adjusted: dict[str, float] = {}
    for tour in ("ATP", "WTA"):
        for family in ("single_variable", "pairwise_context", "uncertainty_ood"):
            family_items = [
                (str(item["candidate_id"]), float(item["raw_discovery_p"]))
                for item in evaluated
                if item["tour"] == tour and item["family"] == family
            ]
            adjusted.update(_bh_adjust(family_items))

    for item in evaluated:
        candidate_id = str(item["candidate_id"])
        q = adjusted[candidate_id]
        item["bh_adjusted_discovery_p"] = q
        concentration = item["validation_concentration_ratio"]
        item["survivor"] = bool(
            int(item["discovery_n"]) >= _MIN_DISCOVERY_N
            and int(item["validation_n"]) >= _MIN_VALIDATION_N
            and bool(item["same_direction"])
            and q < _FDR_ALPHA
            and int(item["validation_years_represented"]) == len(_VALIDATION_YEARS)
            and concentration is not None
            and float(concentration) < 0.5
        )

    evaluated.sort(key=lambda item: (str(item["tour"]), str(item["family"]), str(item["candidate_id"])))
    counts: dict[str, dict[str, dict[str, int]]] = {}
    for tour in ("ATP", "WTA"):
        counts[tour] = {}
        for family in ("single_variable", "pairwise_context", "uncertainty_ood"):
            subset = [item for item in evaluated if item["tour"] == tour and item["family"] == family]
            counts[tour][family] = {
                "generated": len(subset),
                "survivors": sum(bool(item["survivor"]) for item in subset),
            }

    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "exploratory_only": True,
        "production_promotion_allowed": False,
        "discovery_end_year": _DISCOVERY_END_YEAR,
        "validation_years": list(_VALIDATION_YEARS),
        "bootstrap_resamples": _BOOTSTRAP_RESAMPLES,
        "bootstrap_seed_namespace": _BOOTSTRAP_SEED_NAMESPACE,
        "fdr_method": "Benjamini-Hochberg",
        "fdr_threshold": _FDR_ALPHA,
        "minimum_discovery_n": _MIN_DISCOVERY_N,
        "minimum_validation_n": _MIN_VALIDATION_N,
        "input_file_sha256": dict(sorted(observed_hashes.items())),
        "source_validation_bundle_sha256": results_payload.get("bundle_sha256"),
        "source_stage_a_seal_sha256": results_payload.get("stage_a_seal_sha256"),
        "source_outcomes_sha256": results_payload.get("outcomes_sha256"),
        "residual_ledger_sha256": residual_ledger_sha,
        "feature_ledger_sha256": feature_ledger_sha,
        "candidate_counts": counts,
        "candidates": evaluated,
    }
    artifact_sha = _payload_sha(unsigned)
    return {**unsigned, "artifact_sha256": artifact_sha}, residual_rows, feature_rows


def _write_json(value: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_jsonl(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run preregistered residual pattern discovery")
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--residual-ledger", required=True, type=Path)
    parser.add_argument("--feature-ledger", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact, residual_rows, feature_rows = run_pattern_discovery(
        results=args.results,
        pre_match=args.pre_match,
        profile_gap_atp=args.profile_gap_atp,
        profile_gap_wta=args.profile_gap_wta,
        genome_atp=args.genome_atp,
        genome_wta=args.genome_wta,
    )
    _write_json(artifact, args.output)
    _write_jsonl(residual_rows, args.residual_ledger)
    _write_jsonl(feature_rows, args.feature_ledger)
    print(
        json.dumps(
            {
                "experiment_id": artifact["experiment_id"],
                "version": artifact["version"],
                "artifact_sha256": artifact["artifact_sha256"],
                "residual_ledger_sha256": artifact["residual_ledger_sha256"],
                "feature_ledger_sha256": artifact["feature_ledger_sha256"],
                "candidate_counts": artifact["candidate_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
