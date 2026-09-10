# POINTSIM-001 — Mechanistic Point-to-Match Probability Protocol

Status: preregistered before historical result inspection.

## Purpose

Test whether the already-frozen opponent-adjusted serve/return point probabilities contain useful structure when propagated through tennis scoring mechanics, and whether that mechanistic probability adds information beyond the strict Core model.

This experiment is deliberately separated from FUSION-CAL-001. It does not use sportsbook odds, does not tune against the spent partial-2026 holdout, and does not assume that a mechanistic simulator is superior merely because it resembles tennis scoring.

## Data boundary

- Research source: pinned `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Development years: 2000–2025 only
- The partial-2026 holdout is spent and forbidden
- Walkovers excluded
- Retirements excluded in the primary analysis
- Only information available before the target match may enter the prediction
- Serve/return state remains date-frozen exactly as in EXP-003

## Frozen point inputs

For every eligible target match, obtain the pre-match opponent-adjusted point probabilities from the existing EXP-003 state engine:

- `p_a_serve`: probability player A wins a point while A serves
- `p_b_serve`: probability player B wins a point while B serves

No target-match statistics may enter these values.

No new serve/return parameters are tuned in POINTSIM-001. The existing `ServeReturnConfig` remains frozen:

- base service-point win probability: 0.62
- learning rate: 0.50
- reference points: 60

## Mechanistic scoring model

### Service games

Assume independent point outcomes with constant server-specific point probability within the match.

For a server point-win probability `p`, calculate the exact probability of winning a standard advantage game, including the deuce loop.

### Sets

Primary set approximation:

- standard alternating service games
- first to 6 games, win by 2
- at 6–6, play a standard first-to-7-by-2 tiebreak
- first server is not present in the canonical historical source; therefore compute the set probability under A serving first and B serving first and average the two with equal 0.5 weight
- the same averaged set-win probability is used for each set in the match

This is an explicit approximation. Historical tournaments used varying final-set and tiebreak rules, and the current canonical schema does not preserve a verified per-match scoring-rule variable. POINTSIM-001 therefore does **not** claim exact historical scoring-rule reconstruction.

### Match

- best-of-3: first to 2 sets
- best-of-5: first to 3 sets
- match probability is calculated analytically from the averaged set-win probability under independent-set approximation

The experiment must separately report best-of-3 and best-of-5 performance where sample size permits.

## Frozen controls

### S0 — same-input statistical control

Chronological logistic regression using only the same mechanistic input information:

- `logit(p_a_serve)`
- `logit(p_b_serve)`
- best-of-5 indicator

Preprocessing/model fit uses only years before the outer test year.

This control asks whether explicit tennis scoring mechanics improve on a direct statistical remapping of exactly the same point-strength information.

### S1 — POINTSIM probability

The fixed point → game → set → match probability described above. No outcome-fitted mapping is applied for the primary mechanics comparison.

### M0 — Core recalibration control

Chronological logistic model on `logit(p_core)` only.

### M1 — Core + POINTSIM

Chronological logistic fusion using:

- `logit(p_core)`
- `logit(p_pointsim)`

with training-fold-only standardization.

M1 tests whether the mechanistic probability contains incremental information beyond strict Core. Because ATP Core already contains serve/return features, a positive ATP result would demonstrate useful nonlinear/mechanistic transformation beyond the current linear Core representation, not a new independent raw data family. WTA Core excludes serve/return from its strict A-only set, so WTA has a stronger independence interpretation if M1 passes.

## Primary hypotheses and gates

### H-018A — scoring mechanics value

POINTSIM earns a mechanistic-method development pass only if S1 versus S0:

1. improves aggregate Brier score;
2. improves aggregate log loss;
3. jointly wins Brier and log loss in at least 60% of evaluated outer years;
4. does not worsen aggregate Brier over 2021–2025;
5. does not worsen aggregate log loss over 2021–2025.

Failure means the explicit scoring transformation is not preferred over a direct statistical remap of the same inputs.

### H-018B — incremental value beyond Core

Core + POINTSIM (M1) is promoted as a model-stack candidate only if, relative to M0:

1. aggregate Brier improves;
2. aggregate log loss improves;
3. joint Brier + log-loss wins occur in at least 60% of evaluated outer years;
4. 2021–2025 aggregate Brier is not worse;
5. 2021–2025 aggregate log loss is not worse.

A failure on H-018A does not automatically force H-018B to fail: a deterministic nonlinear transform may still provide useful incremental structure. However, if H-018A fails, no claim that tennis scoring mechanics themselves are superior is allowed.

## Diagnostics

Report without changing promotion rules:

- accuracy
- ECE-10
- calibration slope/intercept if available
- best-of-3 versus best-of-5 scores
- serve-point-history depth slices
- probability extremity
- S0/S1 and M0/M1 yearly tables
- 2021–2025 aggregate block

## Adversarial checks

1. Player A/B swap must satisfy `P(A) = 1 - P(B)` within numerical tolerance.
2. Increasing A's serve-point probability while holding B fixed must not decrease A match probability.
3. Increasing B's serve-point probability while holding A fixed must not increase A match probability.
4. Equal point-strength inputs must produce 0.5 match probability after first-server averaging.
5. Outer-year statistical controls may train only on earlier years.
6. Future appended matches must not alter historical serve/return snapshots or historical POINTSIM probabilities.
7. Selected-tour rows after 2025 must fail closed.
8. No target-match stats, score, retirement information, or result may enter a pre-match probability.

## Interpretation limits

A positive result would support a mechanistic probability module built from pre-match serve/return state. It would not prove point independence, exact historical scoring-rule reconstruction, causal player traits, market edge, CLV, ROI, or profitability.

The first-server averaging, independent-point assumption, constant within-match serve strength, and simplified historical tiebreak rules are explicit model assumptions to be challenged in later experiments rather than hidden as facts.
