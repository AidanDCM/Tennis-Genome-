# PATTERN-CONFIRM-001 — Prospective prediction confirmation

Status: FROZEN BEFORE ANY ELIGIBLE POST-CUTOFF OUTCOME IS INSPECTED.

Prospective eligibility cutoff: 2026-09-12T00:00:00-04:00. A match must start on or after this cutoff to contribute confirmatory evidence.

## Fresh-sample rule

The repository records that an earlier partial-2026 holdout was already opened. Therefore no pre-cutoff 2026 match may be described as independent confirmation here. Older 2026 rows may be used only for descriptive engineering or accrual-rate checks that cannot alter this protocol.

## Confirmatory family

Family size: 2. Tour: ATP only.

### PC-ATP-PG-LOW

Source candidate: ATP:single_variable:0914faa2399d38c4.

Frozen eligibility rule:

profile_gap < -0.4045998117259577

Frozen probability correction:

p_corrected = clip(p_market_core - 0.031143878674067826, 1e-6, 1 - 1e-6)

Planning effect magnitude: 0.031143878674067826.
Planning residual SD: 0.4347784219646229.

### PC-ATP-PG-ABS-HIGH

Source candidate: ATP:uncertainty_ood:90451092e0e9a458.

Frozen eligibility rule:

abs(profile_gap) >= 0.47108555150900466

Frozen probability correction:

p_corrected = clip(p_market_core - 0.022734415112664306, 1e-6, 1 - 1e-6)

Planning effect magnitude: 0.022734415112664306.
Planning residual SD: 0.42442004311667597.

A match may satisfy both hypotheses. Overlap does not permit analyst choice or deduplication across hypotheses.

## Frozen baseline

The target remains the residual used in PATTERN-DISCOVERY-001:

residual = outcome_a - p_market_core

p_market_core is the frozen market-plus-Strict-Core probability using the same logistic form as MARKET-EDGE-ADV-001:

logit(p_market_core) = intercept + market_logit_slope * logit(p_market) + core_logit_slope * logit(p_core)

Before prospective accumulation, one future-use market-plus-Core calibration fit must be created from already-open historical out-of-sample component predictions through 2025 and sealed by hash. It may not use any post-2025 outcome and may not be refit during PATTERN-CONFIRM-001.

The Strict Core mapping remains Core v1 strict-A-only and is trained with outcomes through 2025 only. Dynamic player state may update chronologically from genuinely earlier matches, but model features and fitted mapping may not be reselected using prospective confirmation outcomes.

Profile Gap remains the frozen ATP strict representation, with its predictive mapping trained through 2025 only. Future state may evolve chronologically using information available before each target match. The Profile Gap definition, thresholds and corrections may not be retuned.

Market probability must preserve the already-frozen two-sided proportional no-vig semantics and deterministic source policy. Source choice may not depend on hypothesis membership, signal value or outcome.

## Outcome firewall and prospective ledger

Every candidate record must be logged without outcome fields before settlement evaluation. The record contains at minimum canonical match_id, ATP tour, scheduled start, observation time, market source provenance, p_market, p_core, profile_gap, frozen calibration-fit identifier, computed p_market_core, mechanically determined hypothesis memberships and a row digest.

The logger must reject result/outcome/score fields, duplicate match IDs, observation timestamps at or after scheduled start, and scheduled starts before the prospective cutoff.

Walkovers and retirements are excluded from scoring but must remain auditable in settlement accounting rather than silently disappearing.

## Sequential family design

Familywise one-sided alpha: 0.05. Each of the two hypotheses receives Bonferroni one-sided alpha 0.025. This remains valid despite overlap between cells.

Target planning power: approximately 0.90.

Four O'Brien-Fleming efficacy looks are fixed at information fractions 0.25, 0.50, 0.75 and 1.00.

Frozen O'Brien-Fleming constant:

c = 2.0243208652402602

Frozen one-sided Z boundaries:

look 1: 4.0486417304805205
look 2: 2.862822022035254
look 3: 2.337484394530551
look 4: 2.0243208652402602

For a cumulative hypothesis sample:

Z = -mean(residual) / (sample_sd(residual) / sqrt(n))

so larger positive Z supports the historical negative-residual direction.

### PC-ATP-PG-LOW

Maximum planned N: 2,094.
Frozen look Ns: 524, 1,047, 1,570, 2,094.

### PC-ATP-PG-ABS-HIGH

Maximum planned N: 3,744.
Frozen look Ns: 936, 1,872, 2,808, 3,744.

The planning calculation uses the frozen historical effect magnitude, the larger discovery/validation residual SD, this four-look O'Brien-Fleming design and 90% power. These are planning values, not tunable thresholds.

No automatic futility boundary is added in v1.

## Confirmation rule

At each exact chronological look N, evaluate the first N qualifying settled matches ordered by scheduled start and canonical match ID.

A hypothesis is independently confirmed only if, at the same frozen look:

1. one-sided residual Z meets or exceeds that look's O'Brien-Fleming boundary;
2. observed mean residual is negative;
3. the fixed discovery correction improves cumulative Brier score versus p_market_core; and
4. the same fixed correction improves cumulative binary log loss versus p_market_core.

The score requirements are conservative directional gates, not extra significance tests.

If an earlier boundary is not crossed, accumulation continues to the next frozen look. If final maximum N is reached without the full rule, status becomes FAILED_TO_CONFIRM. Optional peeking between looks cannot trigger confirmation.

## Immutable elements

The family, ATP scope, thresholds, fixed corrections, cutoff, model identities and training cutoff, residual definition, exclusions, alpha allocation, look schedule, boundaries, maximum Ns and chronological inclusion rule may not change after this freeze. An implementation bug may be corrected only by a pre-result amendment showing outcome-independent equivalence.

## Interpretation

This is a prediction-confirmation experiment. Passing it would establish that one or both frozen ATP Profile-Gap regimes continue to expose a prospective probability bias beyond the frozen market-plus-Core baseline. Any later decision or economic-use layer is a separate experiment.
