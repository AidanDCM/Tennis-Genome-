# Leakage Rules

Leakage is a project-killing failure mode. A model that sees information unavailable at prediction time can look brilliant while being useless in reality.

## T0 definition

For every prediction define:
- `scheduled_start_at`
- `prediction_cutoff_at`
- `actual_start_at` if known

The canonical pre-match T0 is `prediction_cutoff_at`. No feature may use information with `available_at > prediction_cutoff_at`.

## Availability vs event time

Store both:
- `observed_at`: when the underlying event happened;
- `available_at`: when a predictor could have known it.

Example: an injury happened Monday but was first reported Wednesday. A Tuesday prediction cannot use it.

## Ranking leakage

Historical rows must use rankings/points published and available at T0, not later database snapshots.

## Rolling statistics

All rolling features must exclude the target match and all future matches.

Sort by actual chronology and implement explicit left-closed windows.

Forbidden:
- calculating season average using full season, then attaching it to early-season matches;
- normalization using future-season values;
- using post-match updated Elo as pre-match Elo.

## Elo update order

For match `m`:
1. read pre-match ratings;
2. emit prediction/features;
3. record immutable pre-match rating values;
4. observe outcome;
5. update rating for subsequent matches.

## Tournament/event aggregates

Court/event pace statistics used pre-match must be calculated only from matches completed before T0.

Do not calculate full-tournament hold/ace rate and attach it to first-round matches.

## Player profiles

Profiles are versioned snapshots. A historical match cannot use a later profile version or attributes learned retrospectively.

## Injury/news/context

Each human-context record requires a first-known timestamp and evidence source.

Post-match interviews explaining a pre-match condition cannot be backfilled into the production pre-match feature unless there is separate evidence it was available before T0.

Such retrospective evidence may be stored for research labels, but must be explicitly marked `posthoc_only`.

## Market data

If testing a market-aware policy at a specified decision time, only prices timestamped at or before that decision cutoff may be used.

Closing odds are evaluation data unless the decision is explicitly made at close.

CLV is post-decision evaluation and must never enter pre-match prediction features.

## Scaling / preprocessing leakage

Scalers, encoders, PCA, embeddings, feature selection, imputation models, and calibrators must be fit on training data only within each chronological fold.

## Nearest-neighbor leakage

Historical-neighborhood retrieval for target match `m` may search only matches with data available before `m`'s T0.

No future neighbor is allowed, even if the embedding itself was trained without labels.

## Missingness leakage

Do not fill missing historical values with statistics calculated from future periods.

Imputation parameters must be fitted inside each training fold.

## Cross-validation

Core evaluation uses walk-forward/blocked chronological validation.

Random K-fold may be used only for narrowly scoped diagnostics and never as primary evidence of deployable performance.

## Prediction immutability

Once a prediction is generated, persist:
- model version
- feature version
- data cutoff
- probability
- uncertainty
- decision

Post-match systems append outcomes and evaluation fields but never overwrite original prediction values.

## Automated leakage tests

Required tests should fail the pipeline when:
- any feature timestamp exceeds T0;
- target match appears inside its own rolling history;
- Elo/profile snapshot is dated after T0;
- preprocessing object is fitted using evaluation rows;
- neighbor date is not strictly historical;
- market close price is included in an earlier-decision feature matrix;
- swapped-player consistency breaks unexpectedly;
- feature values change when future rows are appended to the dataset.

## Future-append invariant

A powerful test:

1. compute features for all matches through date D;
2. append matches after D;
3. recompute the same historical features;
4. assert every pre-D feature remains identical.

Any change indicates temporal contamination or unstable data processing.
