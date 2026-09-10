# GENOME-ADV-001 — Adversarial Controls for Historical Alignment

Status: **pre-result protocol**

This protocol is frozen before any GENOME-ADV-001 historical output is inspected.

## Purpose

GENOME-NN-001 established that a transparent k=100 historical residual neighborhood adds small but stable chronological probability value beyond a simple fair meta-control on ATP and WTA.

That result does **not** yet establish that the gain comes from rich matchup geometry. Because the full Genome vector includes the strict Core features themselves, historical neighbors may partly act as a nonlinear / local recalibration of Core probability.

GENOME-ADV-001 asks a narrower adversarial question:

> Does the full Tennis Genome neighborhood add future residual information beyond what can already be recovered from local Core-probability matching and strict-Core-feature matching?

The experiment is designed to falsify an over-strong interpretation of H-011 before any learned metric, embedding, or module-weight optimization is attempted.

## Source and holdout policy

Use the same pinned research snapshot:

`Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`

Development coverage: **2000–2025 only**.

The partial-2026 holdout is spent and MUST NOT be used for model choice, feature choice, k selection, interpretation repair, or independent-forward claims.

ATP and WTA are evaluated separately.

Primary match eligibility:
- non-walkover matches;
- retirements excluded;
- minimum strict-Core training population: 1,000 matches.

## Shared OOS Core residual ledger

All neighborhood controls use the **same** expanding-year out-of-sample strict Core v1 ledger.

For outer year `Y`:
1. train the tour's frozen `strict_a_features(tour)` probability model only on years `< Y`;
2. predict year `Y`;
3. convert prediction and outcome to the existing deterministic Elo-favorite canonical orientation;
4. freeze `p_core_F`, `y_F`, and `r_core_F = y_F - p_core_F`;
5. never refit year-Y probabilities after observing year-Y outcomes.

Only these OOS residuals may become historical neighbor labels.

## Canonical orientation

Reuse the merged GENOME-NN-001 canonical orientation exactly:
- if pre-match `elo_logit > 0`, source A is canonical favorite;
- if `< 0`, source B is canonical favorite;
- exact Elo ties use stable player-ID order.

Every signed Core matchup feature is multiplied by the canonical orientation sign. Probabilities, outcomes, and residual labels use the same orientation.

No control may use source winner/loser ordering.

## Three frozen neighborhood representations

All three representations use the same target rows, same historical residual labels, same year-frozen historical pools, same primary k, and same unweighted residual mean.

### N1 — Core-probability-only neighborhood

Purpose: adversarial local nonlinear calibration control.

Representation:

`Z_prob = [logit(p_core_F)]`

Rules:
- numerical clipping only at `[1e-9, 1 - 1e-9]` before logit;
- fit a StandardScaler on the historical pool from years `< Y` only;
- Euclidean distance in this one-dimensional standardized coordinate;
- no other feature is allowed.

Because this neighborhood uses only Core probability, any signal it recovers cannot be attributed to richer matchup structure.

### N2 — strict-Core-feature neighborhood

Purpose: determine whether the full Genome's absolute Profile-state block adds information beyond local matching on the accepted Core matchup geometry.

Representation:

`Z_core = canonicalized strict_a_features(tour)`

Rules:
- use exactly the frozen tour-specific strict Core v1 feature list;
- historical-fold-only median imputation;
- historical-fold-only standardization;
- Euclidean distance;
- no Profile means, Profile Gap, B/C/D families, ranking, H2H, IOC, or learned features.

### N3 — full Genome neighborhood

Purpose: reproduce the merged transparent Genome v1 candidate.

Representation:
- exact merged `GENOME_VERSION = genome-v1-core-plus-profile-means`;
- canonical strict Core features plus absolute means of strict Player Profile v1 fields;
- historical-fold-only median imputation and standardization;
- Euclidean distance.

No Genome feature, transform, or permission rule may be changed from GENOME-NN-001.

## Historical pool discipline

For target year `Y`, every neighbor candidate must satisfy:
- its strict-Core probability was generated out-of-sample;
- its calendar year is strictly `< Y`;
- its outcome is known;
- it passed the same primary eligibility rules.

Year-Y rows can never become neighbors for another year-Y row.

Minimum historical OOS residual pool: **1,000 rows**.

## Distance and neighborhood size

Primary neighborhood size for all controls: **k = 100**.

Candidate retrieval limit: **1,000** historical rows where applicable.

Primary residual signal for representation `m`:

`R_m(i) = mean(r_core_F(j) for j in N_100^m(i))`

No distance weighting, shrinkage, adaptive k, or learned metric is allowed.

Distance ties are resolved deterministically by historical `match_id`.

No k=25 or k=250 result may influence the GENOME-ADV-001 decision. Those values were already diagnostics in GENOME-NN-001 and are unnecessary for this adversary.

## Fair target population

The primary comparison population for a year contains only rows for which **all three** registered neighborhood signals are available:
- `R_prob`;
- `R_core`;
- `R_full`.

Every pairwise model comparison must score exactly the same future match IDs.

No representation may gain apparent performance by dropping harder rows.

## Chronological meta-models

For each evaluable target year `Y`, meta-training uses only earlier OOS rows that already possess all three legal historical neighborhood signals.

Frozen estimator family for all models:
- `StandardScaler` on meta-training rows only;
- `LogisticRegression`;
- `C=1.0`;
- `solver="lbfgs"`;
- `max_iter=1000`;
- intercept enabled;
- no class weighting.

Minimum prior meta-training population: **1,000 rows**.

### M0 — fair calibration control

Features:

`[logit(p_core_F)]`

### M1 — probability-neighborhood challenger

Features:

`[logit(p_core_F), R_prob]`

### M2 — Core-feature-neighborhood challenger

Features:

`[logit(p_core_F), R_core]`

### M3 — full-Genome challenger

Features:

`[logit(p_core_F), R_full]`

All probabilities are mapped back to original Player-A orientation for final scoring.

## Primary outputs

For M0, M1, M2, and M3 report:
- N;
- Brier;
- binary log loss;
- accuracy;
- ECE-10;
- year-by-year scores;
- 2021–2025 aggregate scores.

Primary interpretation is based on M3 versus M1 and M3 versus M2. M0 remains context for how much local residual methods improve beyond the simple chronological calibration layer.

For each pair, define:

`Delta_Brier(A>B) = Brier(B) - Brier(A)`

`Delta_LogLoss(A>B) = LogLoss(B) - LogLoss(A)`

Positive means A is better.

## Residual diagnostics

For each of `R_prob`, `R_core`, and `R_full`, report:
- N;
- slope of realized future Core residual on the neighbor residual signal;
- equal-count quintiles of signal value;
- Q5-minus-Q1 realized Core residual;
- same slope and spread for 2021–2025.

These diagnostics explain signal shape but do not override proper-score gates.

## Primary interpretation gates

### Gate A — full Genome beats probability-only local correction

M3 clears Gate A only if all are true:
1. aggregate Brier(M3) < Brier(M1);
2. aggregate log loss(M3) < log loss(M1);
3. M3 beats M1 on both Brier and log loss in at least 60% of evaluated years;
4. 2021–2025 aggregate Brier(M3) <= Brier(M1);
5. 2021–2025 aggregate log loss(M3) <= log loss(M1).

### Gate B — full Genome beats strict-Core-feature neighborhood

M3 clears Gate B only if all are true:
1. aggregate Brier(M3) < Brier(M2);
2. aggregate log loss(M3) < log loss(M2);
3. M3 beats M2 on both Brier and log loss in at least 60% of evaluated years;
4. 2021–2025 aggregate Brier(M3) <= Brier(M2);
5. 2021–2025 aggregate log loss(M3) <= log loss(M2).

### Interpretation classes

If Gate A and Gate B both pass:
- classify H-011 as **structured-matchup historical alignment supported beyond local Core correction**;
- still historical-development only;
- learned metrics / module-specific extensions may be considered in a later preregistered experiment.

If Gate A passes but Gate B fails:
- classify H-011 as **Core-geometry local residual correction**;
- the absolute Profile-state block has not proven incremental neighborhood value;
- do not claim richer Profile-aware matchup geometry.

If Gate A fails:
- classify H-011 as **local Core-probability residual correction not isolated from calibration** regardless of Gate B;
- do not escalate Genome complexity.

If M3 loses to both M1 and M2:
- retain GENOME-NN-001 as a valid historical result against its registered control, but downgrade the strong "matchup geometry" interpretation.

## Calibration guardrail

ECE is diagnostic only. A method does not pass because ECE improves, and a proper-score pass is not invalidated solely by modest ECE worsening.

Calibration remains a separate system layer.

## Engineering invariants required before historical execution

- selected-tour post-2025 data fails closed;
- no neighbor year may be `>=` target year;
- all three signals use the same OOS Core residual labels;
- primary k is exactly 100 for all three representations;
- M0/M1/M2/M3 are scored on identical target match IDs;
- preprocessing for every neighborhood representation is fitted only on historical rows;
- meta preprocessing/models are fitted only on earlier meta rows;
- swapping A/B preserves canonical neighborhood coordinates and favorite-oriented targets;
- appending future matches cannot alter already-emitted historical vectors/signals;
- deterministic tie breaking gives repeatable neighbor IDs;
- the full Genome branch reproduces the merged `GENOME_VERSION` representation without mutation.

## Non-claims

GENOME-ADV-001 does not establish:
- independent forward validation;
- causal mechanisms;
- sportsbook mispricing;
- EV, CLV, ROI, or profitability;
- optimal k;
- optimal distance metric;
- optimal feature weights;
- optimal embeddings;
- a live PASS threshold.

## Decision after execution

The result will be recorded exactly against these gates. No post-result feature addition, k change, representation repair, or threshold search may be used to upgrade a failed gate.
