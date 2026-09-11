# PATTERN-DISCOVERY-001 — Amendment 001

Status: **FROZEN BEFORE ANY RESIDUAL PATTERN MINING**

## Trigger

The bookmaker confirmatory family is complete and all four broad Profile Gap / Genome claims failed promotion. Before inspecting any residual pattern, this amendment freezes the exact first implementation of `PATTERN-DISCOVERY-001` so the search space, binning, tests, multiplicity families, and survivor rules cannot be changed in response to attractive-looking discoveries.

No residual-by-feature candidate result has been generated or inspected before this amendment.

## Exact source artifacts

The first discovery run must use only the frozen confirmatory and canonical artifacts below:

- confirmatory workflow run: `34623630174`
- confirmatory code SHA: `6d62014eeb1549c0bda09cb5987695ac7c2be2a1`
- `market_validation_results.json` file SHA-256: `6419f5fbfa24ed6399771ce9a8ed23a46aa8720406acf987498eb24ed139e88d`
- internal validation bundle SHA-256: `be097af8ff9052a1484bdc25fab861d75ada78e21252c7bdb9cfde42ab093a54`
- Stage-A seal SHA-256: `b9260e9ab398dc10bdf358e99d5ca26f61ba3ef0970eca1abc48568ed0508b84`
- outcomes SHA-256: `c509dff1bbe4b1e10944f5b361138790f85ccdb21b7d12aafb03ddc0b1e8c63d`
- canonical `pre_match.parquet` SHA-256: `557e579cd69b04b7436fee342d90d44a3a7e982f128b586ca0e6d1e01b0eec9e`
- ATP Profile projection SHA-256: `8dc6524e70b593fcbc03cc0af0e5d74675dcdff8777af9c693f3df36d07cc472`
- WTA Profile projection SHA-256: `315ae83acf91b58200a09f91a466f4b4ef19b03848175afce3fa86b0be1ce795`
- ATP Genome projection SHA-256: `4e83ffb4f751d901934a4124d215e4dee9ef9eacd9f5c2b9590fd86334e6965b`
- WTA Genome projection SHA-256: `2bc89fbfae1a4ba281fe2f859fb6a72a2ad9fd9702d4a0c172ad3962a50e239f`

The implementation must fail closed if any hash differs.

## Canonical residual ledger

For each tour, the implementation must first verify that the `market_core_probability_a`, outcome, market probability, core probability, year, and match-ID populations in the Profile Gap and Genome adversarial primary reports are **exactly identical**. A single discrepancy aborts discovery.

After that equality check, one deterministic copy is serialized into the residual ledger:

`residual = outcome_a - market_core_probability_a`

The residual baseline is therefore always the frozen chronological Market + Strict Core control.

## Chronology

- discovery block: all eligible years through `2022`
- internal validation block: `2023`, `2024`, `2025`

Quantile boundaries, category eligibility, candidate direction, and correction magnitude are learned from the discovery block only. Validation outcomes may not influence candidate definitions.

## First-implementation feature universe

Only the following legal pre-match quantities may be searched in v1.

### Numeric single-variable features

1. `market_probability_a`
2. `core_probability_a`
3. `market_core_probability_a`
4. `market_core_disagreement = core_probability_a - market_probability_a`
5. `abs_market_core_disagreement`
6. `market_confidence = abs(market_probability_a - 0.5)`
7. `market_core_confidence = abs(market_core_probability_a - 0.5)`
8. `rank_diff = rank_b - rank_a` (positive favors Player A because lower rank is stronger)
9. `abs_rank_diff`
10. `rank_points_diff = rank_points_a - rank_points_b`
11. `abs_rank_points_diff`
12. `age_diff = age_years_a - age_years_b`
13. `abs_age_diff`
14. `height_diff = height_cm_a - height_cm_b`
15. `abs_height_diff`
16. `profile_gap`
17. `abs_profile_gap`
18. `genome_signal`
19. `abs_genome_signal`

Numeric candidates use **discovery-fitted quintile bins**. Duplicate quantile cut points are collapsed deterministically. The frozen cut points are then applied unchanged to 2023-2025.

### Context features

The following direct categorical contexts may generate one candidate per discovery-observed level:

- `surface`
- `tournament_level`
- `round`
- `best_of`

The following fixed market-probability bands are also contexts and are not learned from outcomes:

- `[0.0, 0.2)`
- `[0.2, 0.4)`
- `[0.4, 0.6)`
- `[0.6, 0.8)`
- `[0.8, 1.0]`

Missing values are represented explicitly only for coverage accounting; they do not become an automatically favored candidate state.

## Declared FDR families

ATP and WTA are analyzed separately. Benjamini-Hochberg adjustment is performed independently within each `tour × family` set.

### `single_variable`

- every quintile cell of every numeric feature above;
- every observed direct categorical context above;
- every fixed market-probability band.

### `pairwise_context`

Only these deterministic interactions are permitted in v1:

- discovery-fitted tertile of `market_core_disagreement` × `surface`;
- discovery-fitted tertile of `abs_market_core_disagreement` × fixed market-probability band;
- discovery-fitted tertile of `rank_diff` × `surface`;
- discovery-fitted tertile of `profile_gap` × `surface`;
- discovery-fitted tertile of `genome_signal` × `surface`.

Every Cartesian cell generated from the discovery-fitted bins counts in the family, including rejected cells.

### `uncertainty_ood`

The initial uncertainty/OOD family is deliberately limited to legal descriptors already available in the sealed artifacts:

- quintiles of `abs_market_core_disagreement`;
- quintiles of `market_confidence`;
- quintiles of `market_core_confidence`;
- quintiles of `abs_profile_gap`;
- quintiles of `abs_genome_signal`;
- tertile(`abs_market_core_disagreement`) × tertile(`market_core_confidence`);
- tertile(`abs_profile_gap`) × tertile(`abs_genome_signal`).

This first implementation does not claim to exhaust neighborhood-density/OOD features. Adding new uncertainty features requires another prospective discovery amendment.

## Candidate statistic

A candidate is a fixed subset/cell. Its primary exploratory effect is:

`mean(residual)` within that cell.

The discovery null is `mean(residual) = 0`, tested two-sided with a one-sample t-test. If fewer than two finite discovery residuals are present or variance makes the statistic undefined, raw p is set to `1.0` and the candidate cannot survive.

Every generated candidate receives a raw p-value and is included in BH correction for its declared `tour × family` set regardless of whether it later fails sample-size or stability requirements.

## Bootstrap uncertainty

- percentile bootstrap
- `2,000` resamples
- 95% interval
- deterministic global seed namespace `1729`
- candidate-specific seed = deterministic SHA-256-derived integer from `PATTERN-DISCOVERY-001|tour|family|candidate_id|1729`

Discovery and validation mean-residual confidence intervals are both reported.

## Survivor rule

The original protocol thresholds remain load-bearing. A candidate survives only if all are true:

- discovery candidate-cell N >= `500`;
- validation candidate-cell N >= `300`;
- discovery and validation mean residuals have the same non-zero sign;
- BH-adjusted discovery p < `0.10` within its tour × family;
- all three validation years 2023-2025 are represented;
- largest absolute validation-year residual-sum contribution is < `50%` of the sum of absolute validation-year residual-sum contributions;
- deterministic definition and all provenance checks pass.

For pairwise cells, the cell itself is the reported primary cell and must satisfy the same N thresholds; no post-result cell merging is permitted.

## Earlier-year-fitted probability diagnostic

For each candidate, the simple exploratory correction magnitude is the discovery mean residual.

On that candidate's 2023-2025 validation matches only:

`p_corrected = clip(p_market_core + discovery_mean_residual, 0.001, 0.999)`

The artifact reports baseline vs corrected Brier score, log loss, and a fixed-width 10-bin reliability table. These are diagnostics only and cannot override the survivor rule.

## Annual contribution definition

For survivor stability, validation annual contribution for year `y` is:

`sum(residual_i)` over candidate matches in year `y`.

The concentration ratio is:

`max(abs(contribution_y)) / sum(abs(contribution_y))`

If the denominator is zero, the concentration gate fails.

## Reproducibility

The v1 artifact must contain:

- exact input file hashes and internal bundle/seal hashes;
- exact candidate-generator version `pattern-discovery-v1`;
- every generated candidate, accepted or rejected;
- quantile/tertile cut points;
- raw and BH-adjusted p-values;
- bootstrap seeds and intervals;
- discovery/validation Ns, effects, year contributions, missingness and market-probability summaries;
- validation Brier/log-loss/reliability diagnostics;
- candidate counts by tour × family;
- deterministic artifact self-hash.

No candidate from this run is independently confirmed or production-eligible. Survivors may only seed new frozen hypotheses with a new untouched future boundary.
