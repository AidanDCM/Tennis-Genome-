# PROFILE-GAP-001 — Player Profile Strength and Profile Gap

Status: **pre-result protocol**

This experiment is registered before any PROFILE-GAP-001 historical result is inspected.

## Question

Can a compact, time-versioned player-state representation learn a player strength score that improves on overall Elo, and does the difference between profile-derived strength and Elo-implied strength predict future Elo residuals?

This is the operational test of H-009:

> Players whose validated underlying profile state is stronger than their Elo-implied state should subsequently outperform Elo expectation, while players whose profile state is weaker should underperform it.

The counter-hypothesis is that Profile Gap is merely noisy recent form or a repackaging of Elo with no stable incremental future value.

## Non-goals

PROFILE-GAP-001 does **not** test:
- sportsbook value, EV, CLV, or profitability;
- injuries, news, coaching changes, detailed style, or environment data absent from the current source;
- pure Surface Elo;
- a hard betting/PASS policy;
- the Tennis Genome nearest-neighbor hypothesis itself.

## Source and holdout policy

Use the same pinned CC BY-NC-SA research snapshot used by the foundational laboratory and CAL-SEL-001:

`Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`

Historical development coverage: **2000–2025 only**.

The partial-2026 holdout has already been opened by earlier milestones. It is spent and MUST NOT be used to choose Profile v1 features, tune Profile Strength, define Profile Gap thresholds, repair a failed result, or claim independent forward confirmation.

## Profile state

For every eligible historical match date, create a Player Profile v1 snapshot separately for Player A and Player B using only information legal before that source date. Current-date outcomes and statistics update state only after every profile on the date has been frozen.

Future-append invariant:

> Appending matches after date D must not change any profile value or profile hash already emitted through D.

Profile storage and predictive permission remain separate. A field can exist in the profile while being forbidden from Profile Strength.

## Player-side feature transforms

Profile Strength is deliberately a **player-side scalar**, not an arbitrary hand-written score. The model learns weights chronologically from paired outcomes.

For a player snapshot, candidate numeric transforms are:

### Both tours — strict
- `elo_rating`
- `form_result_30`
- `form_result_90`
- `form_point_30`
- `form_point_90`
- `event_gap_days`
- `log1p(minutes_7)`
- `log1p(minutes_14)`
- `log1p(minutes_28)`
- `matches_14`
- `matches_28`
- `log1p(previous_event_minutes)`

### ATP strict additions
- `serve_rating`
- `return_rating`
- `age_years`
- `(age_years - 27)^2`
- `1(age_years <= 23)`
- `1(age_years >= 32)`
- `height_cm`

The ATP age × fatigue family is B/Conditional and therefore its explicit interaction terms are not included in strict Profile Strength.

### WTA conditional diagnostic only
Add:
- `serve_rating`
- `return_rating`

This diagnostic may describe whether the previously B-graded serve/return family helps the profile representation. It cannot promote that family to WTA Core.

### Explicit exclusions
- ranking and ranking points: descriptive context only;
- handedness: registered representation is D/Rejected;
- IOC/country: identity/context only;
- WTA age/height: C/unstable or unpromoted in the frozen grades;
- source-depth descriptors: uncertainty/data-quality research only, not strength;
- surface/tournament fields: match-context model, not intrinsic player profile;
- H2H and age × fatigue: B families, outside strict Profile Strength.

## Missing values and preprocessing

All preprocessing is fit on training history only.

For each outer test year Y:
1. collect eligible training matches strictly before Y;
2. fit per-feature median imputers using **player-side training profiles only**;
3. fit per-feature standardization using the imputed player-side training profiles only;
4. transform Player A and Player B separately;
5. form the pairwise training vector `z_a - z_b`;
6. fit L2 logistic regression with `C=1.0`, `solver=lbfgs`, `max_iter=1000`, and `fit_intercept=False`;
7. predict year Y from profiles frozen before each target match/date.

No missingness indicators are added to Profile Strength. Missingness/data depth belongs to the uncertainty layer and H-017, not the strength score.

`fit_intercept=False` is required so the representation is player-order symmetric and the learned match logit is exactly the difference of two player-side scores.

## Profile Strength

Let the fitted standardized player vector be `z_i` and learned coefficient vector be `beta`.

Individual profile strength:

`S_profile(i) = beta · z_i`

For players A and B:

`logit(p_profile_A) = S_profile(A) - S_profile(B)`

and therefore swapping A/B must negate the logit and invert the probability.

## Elo Strength

With Elo scale 400 and initial rating 1500, define the individual Elo log-odds coordinate:

`S_elo(i) = (elo_i - 1500) * ln(10) / 400`

Then:

`logit(p_elo_A) = S_elo(A) - S_elo(B)`

## Profile Gap

Individual gap:

`G(i) = S_profile(i) - S_elo(i)`

Match-relative gap:

`G_AB = G(A) - G(B)`

Equivalently:

`G_AB = logit(p_profile_A) - logit(p_elo_A)`

Positive `G_AB` means the profile model considers A stronger relative to B than Elo does. Negative means the reverse.

No manually chosen point values or hand-set feature weights are allowed.

## Eligibility

Primary analysis:
- non-walkover matches;
- retirements excluded, matching the existing primary model convention;
- profiles must be constructible under frozen-date semantics;
- both outcome classes must exist in each training block;
- minimum training sample: 1,000 matches.

The strict model may use median imputation for permitted profile fields. Data-depth strata are reported separately.

## Chronological evaluation

Outer evaluation is expanding-window by calendar year.

For each year Y:
- train only on years `< Y`;
- fit imputation/scaling only on player profiles from years `< Y`;
- fit Profile Strength only on matches from years `< Y`;
- freeze the resulting mapping before predicting Y;
- store immutable probabilities, profile scores, Elo scores, gaps, and outcomes.

No random cross-validation is accepted as primary evidence.

## Controls

At minimum report:
1. **Elo control** — overall Elo probability;
2. **Profile Strength strict** — registered A-grade player-side fields only;
3. **WTA Profile Strength + conditional serve/return** — secondary diagnostic only;
4. **strict Core v1** — contextual benchmark where available, but not the primary H-009 comparator because Core v1 contains match-context features that are intentionally outside Player Profile v1.

## Primary probability metrics

For Elo and Profile Strength:
- Brier score;
- binary log loss;
- accuracy;
- ECE-10 as descriptive calibration evidence;
- sample size;
- annual Brier/log-loss deltas.

Primary improvement signs are defined as:

`Delta_Brier = Brier(Elo) - Brier(Profile)`

`Delta_LogLoss = LogLoss(Elo) - LogLoss(Profile)`

Positive means Profile Strength is better.

## Profile Gap residual test

For every out-of-sample match define Elo residual:

`r_elo = y_A - p_elo_A`

Evaluate the relationship between `G_AB` and future `r_elo` using only out-of-sample predictions.

Registered summaries:
- equal-count Profile Gap quintiles;
- N, mean gap, mean Elo residual, realized A win rate, mean Elo probability per quintile;
- linear slope of Elo residual on Profile Gap as a descriptive directional statistic;
- top-minus-bottom quintile mean Elo residual;
- same summaries for 2021–2025.

The expected H-009 direction is monotonic: more-positive gap should correspond to more-positive Elo residual.

## Data-depth diagnostics

Without changing Profile Strength, stratify results by prior-history depth using information already stored in Profile v1:
- minimum prior matches across both players;
- minimum prior serve/return point history when relevant;
- complete vs incomplete 14-day duration coverage.

These are uncertainty diagnostics only. Thresholds may not be promoted from this same result without a new preregistered experiment.

## Promotion rules

Because no untouched future holdout remains, PROFILE-GAP-001 can produce at most a **development candidate**, not final A/Core promotion.

A strict Profile Strength candidate survives historical development only if all are true:
1. aggregate `Delta_Brier > 0`;
2. aggregate `Delta_LogLoss > 0`;
3. Profile Strength beats Elo on both Brier and log loss in at least 60% of evaluated years;
4. 2021–2025 aggregate Brier and log loss are not worse than Elo;
5. player-order symmetry tests pass;
6. future-append and same-date leakage invariants pass.

H-009/Profile Gap receives provisional support only if, in addition:
1. top-minus-bottom gap-quintile Elo residual is positive in the registered direction;
2. the residual-vs-gap slope is positive in aggregate;
3. the same direction does not reverse in 2021–2025.

Failure of Profile Strength to beat Elo means Profile Gap is not promoted merely because a subgroup or isolated quintile looks attractive.

## Interpretation guardrails

A positive result means the registered player-state representation contains incremental historical predictive information beyond Elo under chronological evaluation.

It does **not** mean:
- the gap is causal;
- the gap is a betting edge;
- a specific gap threshold is profitable;
- the result will survive new future data;
- the current source/license is production-compatible.

A negative result is useful: Profile v1 can still serve as a structured representation and Tennis Genome substrate even if a single scalar Profile Strength fails to improve Elo.

## Next after this experiment

Regardless of outcome, preserve the immutable Profile v1 representation and results. If Profile Gap survives, freeze it as a candidate uncertainty/trajectory signal for future confirmation. Then proceed to the historical-neighborhood Tennis Genome experiment, where similarity is tested on structured profile/match-state vectors rather than rendered images.
