# GENOME-NN-001 — Historical Neighborhood Residual Signal and Density

Status: **pre-result protocol**

This protocol is frozen before any GENOME-NN-001 historical result is inspected.

## Questions

GENOME-NN-001 tests two separate hypotheses.

### H-011 — historical neighbors add incremental residual signal

> Matches that are close in a leakage-safe Tennis Genome representation should have residual performance patterns that help predict future outcomes beyond the accepted parametric Core v1 probability model.

The null/counter-hypothesis is that nearest-neighbor residual effects disappear once Core v1 has already modeled overall strength, form, workload, physical state, and validated match context.

### H-012 — neighborhood density predicts reliability

> Core v1 should be less reliable in sparse / historically unfamiliar regions of Genome space than in dense, familiar regions.

The counter-hypothesis is that kNN distance is merely a geometric artifact with no stable relationship to future forecast error.

## Non-goals

This experiment does **not** test:
- sportsbook prices, EV, CLV, ROI, or profitability;
- a hard PASS/bet threshold;
- learned embeddings, PCA, Mahalanobis distance, or metric learning;
- UMAP/t-SNE as evidence;
- motif mining;
- injuries/news/environment variables not present in the current source;
- arbitrary image/waveform similarity.

Those are later experiments only if the transparent v1 neighborhood survives.

## Source and holdout policy

Use the same pinned research snapshot:

`Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`

Development coverage: **2000–2025 only**.

The partial-2026 holdout is spent and MUST NOT be used to choose Genome features, k, distance weighting, density thresholds, repair a failed result, or claim independent forward confirmation.

ATP and WTA are evaluated separately.

Primary match eligibility:
- non-walkover matches;
- retirements excluded;
- minimum historical Core training population: 1,000 matches.

## Baseline residual ledger

First create the same expanding-calendar-year strict Core v1 probability ledger used by the project’s historical evaluation discipline.

For outer year `Y`:
1. build legal pre-match foundational state for the full eligible history;
2. train the tour’s frozen `strict_a_features(tour)` probability model only on years `< Y`;
3. predict every eligible match in year `Y`;
4. freeze `p_core_A` and the outcome;
5. never refit that year’s Core probabilities after observing year-Y outcomes.

The historical residual attached to a completed ledger row is:

`r_core_A = y_A - p_core_A`

Neighbor labels come only from these genuinely out-of-sample Core residuals. In-sample fitted residuals are forbidden.

## Canonical orientation

Nearest-neighbor geometry must not depend on arbitrary source Player-A / Player-B ordering.

Every match is converted to a deterministic **Elo-favorite orientation** before similarity is computed.

Let `elo_logit` be the pre-match A-vs-B Elo logit from `FoundationalSnapshot`.

- if `elo_logit > 0`, orientation sign = `+1`;
- if `elo_logit < 0`, orientation sign = `-1`;
- if `elo_logit == 0`, the lexicographically smaller stable player ID is the canonical first player.

Every signed strict-Core matchup feature is multiplied by this orientation sign.

The Core probability/outcome/residual are also expressed in canonical orientation:
- if sign = `+1`: `p_core_F = p_core_A`, `y_F = y_A`;
- if sign = `-1`: `p_core_F = 1 - p_core_A`, `y_F = 1 - y_A`;
- `r_core_F = y_F - p_core_F`.

Swapping source A/B must therefore leave the canonical Genome representation and canonical neighbor target unchanged, apart from stable metadata.

## Genome v1 representation

The primary vector deliberately contains both **relative matchup structure** and **absolute player-state level**.

Difference-only fingerprints are insufficient because two evenly matched elite players and two evenly matched weak players can both have near-zero deltas.

### Block 1 — frozen strict Core matchup features

Use exactly `strict_a_features(tour)` from the merged Core v1 specification.

These are the already-graded A-family signed matchup/context representations. After Elo-favorite canonicalization, they become favorite-relative.

No B/C/D family is allowed into primary Genome v1.

### Block 2 — absolute player-state means

Use the player-side transformed fields from the tour’s **strict** `profile_strength_feature_names(tour, include_conditional=False)` representation.

For each permitted player-side field `x`:

`mean_x = (x_A + x_B) / 2`

when both sides are observed; otherwise it remains missing for fold-fitted imputation.

This block provides absolute level/state without adding hand-written predictive weights.

Important:
- ATP uses its strict Profile v1 fields, including validated serve/return and age/physical fields;
- WTA strict excludes conditional serve/return and unstable age/physical fields;
- ranking/ranking points, handedness, IOC, H2H, B-grade age×fatigue, and rejected families stay out;
- Profile Gap itself is **not** included in primary Genome v1, preventing H-009 from mechanically defining H-011.

### Data-quality values

Missingness and history-depth descriptors are recorded for uncertainty diagnostics but are not dimensions in the primary distance metric.

## Fold-fitted preprocessing

For each neighbor target year `Y`, fit preprocessing **only on the historical neighbor pool from years `< Y`**.

Steps:
1. median-impute each Genome dimension on the historical pool only;
2. no missingness indicators in the primary distance vector;
3. standardize each dimension to training-pool zero mean / unit variance;
4. transform the historical pool and year-Y targets with those frozen transforms.

No full-history scaler, PCA, imputer, distance normalization, or other future-fitted transform is allowed.

## Historical neighbor pool

Only rows satisfying all of the following may be neighbors for target year `Y`:
- their Core prediction was itself generated out-of-sample;
- their calendar year is strictly `< Y`;
- their outcome is already known;
- they passed the same primary eligibility rules.

This year-frozen rule is intentionally stricter than merely `date < T0`. It prevents within-test-year online adaptation and makes the first Genome test maximally clean.

A later experiment may test date-strict online updating if exact source timing becomes reliable enough.

Minimum historical residual pool before a target year can be evaluated: **1,000 rows**.

## Distance and k

Primary distance:
- Euclidean distance;
- on the fold-standardized Genome v1 vector;
- every standardized dimension receives equal v1 weight;
- no learned metric and no hand-tuned family weights.

Primary neighborhood size: **k = 100**.

Secondary diagnostics only:
- `k = 25`;
- `k = 250`.

Only k=100 may determine the primary H-011/H-012 decision. The secondary k values may not replace it after results are seen.

Distance ties are broken deterministically by historical `match_id`.

## Neighbor residual signal

For target match `i`, with k historical neighbors `N_k(i)`:

`R_NN(i) = mean(r_core_F(j) for j in N_k(i))`

Primary v1 uses an **unweighted** mean. Distance weighting/shrinkage is deliberately deferred so the first result has no hidden bandwidth parameter.

Also record:
- nearest-neighbor distance;
- mean distance across k=100;
- 100th-neighbor distance;
- fraction of the 100 neighbors that share at least one player with the target;
- target Genome missing fraction before imputation.

## Fair predictive comparison

The raw strict Core model remains a reference, but the primary incremental test compares two nested chronological meta-models so the neighbor challenger does not receive an unfair extra calibration stage.

For each evaluable year `Y`, using only **earlier out-of-sample rows that already possess historical neighbor summaries**:

### Meta-control

L2 logistic regression:

`P(y_F=1) = logistic(alpha + beta * logit(p_core_F))`

### Genome challenger

Same estimator/hyperparameters with one additional feature:

`P(y_F=1) = logistic(alpha + beta1 * logit(p_core_F) + beta2 * R_NN)`

Frozen estimator settings:
- `LogisticRegression`;
- `C = 1.0`;
- `solver = lbfgs`;
- `max_iter = 1000`;
- intercept enabled;
- no class weighting.

Minimum prior meta-training rows: **1,000**.

The fitted models are frozen before year Y and predicted probabilities are mapped back to original Player-A orientation for scoring.

## H-011 registered outputs

Report for raw Core, fair meta-control, and Genome challenger:
- N;
- Brier;
- binary log loss;
- accuracy;
- ECE-10;
- annual scores;
- 2021–2025 aggregate scores.

Primary incremental signs:

`Delta_Brier_NN = Brier(meta-control) - Brier(Genome challenger)`

`Delta_LogLoss_NN = LogLoss(meta-control) - LogLoss(Genome challenger)`

Positive means neighborhood signal adds value beyond the fair control.

Also report direct residual diagnostics:
- slope of actual future `r_core_F` on `R_NN`;
- equal-count quintiles of `R_NN` with mean predicted neighbor residual and realized Core residual;
- Q5-minus-Q1 realized Core residual;
- same summaries for 2021–2025.

## Shared-player adversarial sensitivity

A neighborhood can look useful merely because it repeatedly retrieves the same players.

Therefore record the primary same-player fraction and perform a secondary adversarial sensitivity in which neighbors sharing **either target player** are excluded before selecting k=100.

This sensitivity is not the primary model. Its role is to determine whether a positive result is dominated by player identity rather than transferable matchup structure.

If fewer than 100 non-sharing historical candidates exist, that target is omitted only from this sensitivity view, never from the primary population.

## H-012 density diagnostics

Primary density coordinate:

`D_100 = mean Euclidean distance to the 100 primary neighbors`

Higher `D_100` means a more historically unusual / sparse target.

Evaluate density against the **raw strict Core** forecast error, not the Genome challenger, to avoid circularly defining uncertainty using the model it may later modify.

Registered summaries:
- equal-count D_100 quintiles;
- N, mean D_100, raw-Core Brier contribution, raw-Core log-loss contribution, accuracy, mean absolute Core residual per quintile;
- linear slope of per-match Core log loss on D_100;
- linear slope of absolute Core residual on D_100;
- Q5-minus-Q1 Core log loss;
- same direction checks for 2021–2025.

No density cutoff becomes a PASS rule in this experiment.

## Promotion / interpretation gates

Because no untouched future holdout remains, this experiment can create only historical development candidates.

### H-011 receives provisional support only if all are true
1. aggregate `Delta_Brier_NN > 0` for k=100;
2. aggregate `Delta_LogLoss_NN > 0` for k=100;
3. Genome challenger beats the fair meta-control on both Brier and log loss in at least 60% of evaluated years;
4. 2021–2025 aggregate Brier and log loss are not worse than the meta-control;
5. residual-vs-neighbor-signal slope is positive;
6. R_NN Q5-minus-Q1 realized Core residual is positive;
7. the registered direction does not reverse in 2021–2025;
8. all temporal/orientation/future-append invariants pass.

A positive primary result accompanied by collapse under shared-player exclusion is classified **identity-dependent / conditional**, not general historical-alignment evidence.

### H-012 receives provisional support only if
1. aggregate Core log-loss slope vs D_100 is positive;
2. aggregate absolute-residual slope vs D_100 is positive;
3. highest-density-distance quintile has worse Core log loss than the lowest-distance quintile;
4. the direction does not reverse in 2021–2025.

Density may become an uncertainty candidate, not an automatic abstention rule.

## Engineering invariants

Required tests before historical execution:
- no neighbor year may be `>=` target year;
- swapping A/B yields the same canonical Genome vector;
- swapping A/B negates original-orientation residuals but preserves favorite-oriented residuals;
- preprocessing is fit only on historical rows;
- future-appended matches cannot change previously emitted Genome vectors;
- deterministic tie-breaking produces repeatable neighbor IDs;
- primary k is exactly 100 in the registered run;
- post-2025 selected-tour data is rejected by experiment code;
- shared-player exclusion never leaks target outcomes or future matches.

## Interpretation guardrails

A positive result would mean a transparent historical neighborhood contains incremental **historical predictive structure** beyond the fair parametric control.

It would not establish:
- causality;
- sportsbook mispricing;
- profitability;
- a live bet threshold;
- that Euclidean distance is optimal;
- that visual Genome similarity is predictive;
- independent forward confirmation.

A negative result is also valuable: it would tell us not to spend complexity budget on sophisticated embeddings until a simpler historical-alignment baseline can justify them.
