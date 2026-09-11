# PATTERN-DISCOVERY-001 — Residual Structure Discovery Protocol

Status: **PREREGISTERED BEFORE MARKET STAGE-B RESULTS**

## Purpose

After the frozen market-confirmation family is executed and recorded, begin a deliberately exploratory program to discover repeatable pre-match states in which the strongest frozen baseline systematically under- or over-predicts outcomes.

This experiment is a **hypothesis generator**, not an independent confirmation experiment. Every discovered pattern remains a candidate until it is separately frozen and tested on data not used to discover it.

## Discovery target

For market-covered matches, the default discovery baseline is the chronological `Market + frozen Strict Core` control already defined by `MARKET-EDGE-ADV-001`.

For match `i`:

```text
residual_i = outcome_i - p_market_core_i
```

Positive residual means Player A won more often than the frozen Market + Core probability expected. Negative residual means Player A won less often than expected.

The pattern miner must never substitute a weaker baseline merely because doing so produces larger-looking patterns.

The existing Profile Gap and Genome confirmatory results do not determine this baseline. `Market + Strict Core` remains the residual target whether those signals pass or fail Stage B.

## Population

Primary exploratory population:

- ATP and WTA analyzed separately;
- completed non-walkover/non-retirement matches under the same frozen market population used by the bookmaker validation where the required feature is available;
- years through 2025 only for historical discovery;
- no 2026 result may be treated as a new untouched holdout because prior project work has already spent parts of 2026.

Patterns may have smaller feature-specific populations because not all historical features have equal coverage. Every candidate must report its exact denominator and missingness.

## Permitted feature universe

Only information legally available before the match may define a pattern. Candidate variables may include already-versioned pre-match quantities from these families:

- ranking and ranking-point state;
- overall and surface strength state;
- serve/return strength state;
- recent-form state;
- rest/workload/fatigue state;
- tournament level, round and surface;
- pre-match player-age/career-state variables where already legal and available;
- head-to-head variables only in their already-shrunk pre-match form;
- frozen Player Profile coordinates and Profile Gap;
- frozen Strict Core probability and component geometry;
- frozen Genome neighborhood residual/density/OOD descriptors;
- model disagreement and uncertainty descriptors;
- bookmaker market probability and market-overround descriptors that are part of the frozen pre-match quote artifact;
- deterministic interactions among the above.

Forbidden candidate information includes winner/result labels as features, score, match duration, retirement knowledge not available pre-match, future rankings/statistics, later-match data, future-neighbor membership, and any post-start market information.

## Candidate families

The initial miner may generate candidates from:

1. **single-variable monotonic structure** — fixed quantile bins and rank correlation with residual;
2. **nonlinear single-variable structure** — fixed quantile-bin residual curves;
3. **pairwise interactions** — deterministic Cartesian combinations of coarse bins;
4. **context-conditioned effects** — surface, tournament level, round, ranking band and market-probability band;
5. **disagreement/OOD states** — combinations of model disagreement, neighborhood density and confidence;
6. **style/state combinations** — interactions among already-accepted pre-match feature families;
7. **regime stability** — whether candidate direction repeats across years rather than appearing in one period only.

The engine may not search arbitrary hand-entered thresholds after viewing results. Thresholds must come from a deterministic generator such as fixed-width bins, training-fitted quantiles, or explicitly versioned tree rules.

## Discovery / internal validation chronology

Historical pattern mining must preserve chronology.

Initial split:

- **discovery years:** through 2022;
- **internal validation years:** 2023-2025.

A candidate is generated and its direction is chosen using discovery years only. The 2023-2025 block is then used only to ask whether that fixed candidate repeats in the same direction.

This internal validation is still not independent future confirmation because the overall historical archive has been heavily researched. It is only a defense against immediate in-sample pattern chasing.

## Minimum evidence for a candidate survivor

A candidate may enter the hypothesis ledger only if all of the following are true:

- deterministic definition with no outcome-informed manual threshold;
- discovery sample size >= 500 matches overall and >= 100 in every reported primary cell;
- validation sample size >= 300 matches overall and >= 75 in every reported primary cell;
- same signed residual direction in discovery and 2023-2025 validation;
- not driven by one calendar year: the largest absolute annual contribution is < 50% of total absolute contribution;
- at least 3 separate validation years represented when coverage permits;
- Benjamini-Hochberg FDR-adjusted discovery p-value < 0.10 within the declared candidate family;
- effect size and uncertainty are recorded, not only p-value;
- candidate definition and population are written to the ledger unchanged before any later confirmation.

Failure of these thresholds means the candidate remains rejected/diagnostic. Thresholds are intentionally stricter than merely finding a nominal p-value.

## Statistical outputs

For each generated candidate report:

- definition and feature provenance;
- discovery and validation N;
- mean residual / residual contrast;
- bootstrap confidence interval for the residual contrast;
- raw discovery p-value;
- family-level Benjamini-Hochberg adjusted p-value;
- annual residual contributions;
- discovery/validation sign agreement;
- market-probability distribution;
- Brier/log-loss diagnostic when the pattern is converted to a simple earlier-year-fitted correction;
- reliability table for any probability correction;
- missingness/coverage description.

## Multiple-search accounting

Every generated candidate counts toward its declared discovery family, including rejected candidates. The engine must preserve the full candidate ledger and may not report only winners.

The first implementation must at minimum maintain separate FDR families for:

- single-variable patterns;
- pairwise/context interactions;
- uncertainty/OOD patterns.

Future search families require a protocol amendment before execution.

## No automatic production promotion

`PATTERN-DISCOVERY-001` cannot promote a betting rule, feature, threshold, model change, or production policy.

A surviving candidate becomes a new numbered hypothesis with:

- exact formula/definition;
- target tour/population;
- frozen direction;
- frozen metrics and rejection criteria;
- an untouched future confirmation boundary.

Only that later confirmation can promote the candidate.

## Future confirmation boundary

Because historical 2000-2025 data and portions of 2026 have already been used by prior project work, the project must establish a new forward cutoff before calling any newly discovered pattern independently confirmed.

The specific future cutoff and minimum match count must be frozen in the candidate's own confirmation protocol before those outcomes are used.

## Relationship to POINTSIM

WTA POINTSIM remains historical-development evidence and is not silently promoted by this discovery program. Its future confirmation should be treated as a separate frozen hypothesis alongside any new pattern candidates.

## Reproducibility requirements

The pattern-discovery artifact must include:

- exact Stage-B / Market+Core residual-ledger input hash;
- exact feature-ledger input hash;
- protocol/version identifier;
- complete generated-candidate count by family;
- all accepted and rejected candidates;
- deterministic random seeds for bootstrap/permutation operations;
- artifact self-hash.

Rerunning the same version on the same inputs must reproduce candidate definitions and decisions exactly.
