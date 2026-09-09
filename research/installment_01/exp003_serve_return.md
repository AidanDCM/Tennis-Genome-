# EXP-003 — Elo + Opponent-Adjusted Serve/Return

Status: **registered; real-data run in progress**

## Research question

Does a chronologically learned, opponent-adjusted serve/return matchup signal improve future pre-match probability quality beyond overall Elo?

This is a predictive-information experiment, not a betting-profitability test.

---

## Null / alternative

**H0:** Adding the serve/return matchup signal to Elo does not improve future probability quality.

**H1:** The serve/return signal improves future Brier score and/or log loss with enough stability to justify promotion into the core feature stack or a conditional submodel.

Accuracy is secondary. A change is not promoted because it happens to classify slightly more winners while producing worse probabilities.

---

## Information boundary

The source match row contains both pre-match information and statistics produced during the match. EXP-003 therefore requires three physically separate canonical tables:

- `*_pre_match.parquet`
- `*_outcomes.parquet`
- `*_stats.parquet`

The stats table is post-match evidence. It contains service-point aggregates but not the outcome label. Its filename and SHA-256 are recorded in the canonical manifest and explicitly verified by EXP-003 before use.

The target match's own statistics may update future player state only after the target date. They are never legal target-match features.

---

## Point-strength model

The version-1 serve/return state treats every service-point aggregate as a contest between:

- server serve strength, and
- receiver return strength.

For a server `s` and receiver `r`:

`p(server wins point) = sigmoid(base_logit + serve_rating[s] - return_rating[r])`

The observed service-point win rate produces an opponent-adjusted residual. The residual is split symmetrically between the server's serve rating and receiver's return rating.

This means a 68% service-points-won match is not treated identically against every receiver: the update depends on the return strength expected before that date.

---

## Fixed version-1 configuration

Registered before inspecting the final EXP-003 result:

- base service-point win probability: `0.62`
- learning rate: `0.50`
- reference service-point count: `60`
- update weight: `min(service_points / 60, 1)`
- server receives half the residual update
- receiver receives the opposite half
- walkovers excluded
- primary view excludes retirements

These values are not claimed to be optimal. Parameter tuning is a separate future hypothesis and may not rewrite EXP-003 v1 after the result is known.

---

## Same-date timing rule

The historical source generally provides tournament/event dates rather than trustworthy match start timestamps.

Therefore:

1. all matches sharing a canonical date see the same pre-date serve/return state,
2. all service-point residuals for that date are accumulated,
3. updates are applied only after every prediction for that date is frozen.

This is intentionally conservative. It can discard legitimately available within-event information, but it cannot invent chronology from CSV row order.

---

## Challenger construction

EXP-003 does not compare an uncalibrated two-feature model against raw Elo.

For each test year:

- training rows come only from earlier years,
- baseline logistic model receives Elo log-odds only,
- challenger logistic model receives Elo log-odds + serve/return matchup edge,
- both models use the same training population,
- feature standardization is fitted only on the historical training fold,
- both are evaluated on the exact same future match IDs.

This makes the test specifically ask whether serve/return adds information beyond Elo rather than whether one model received a better calibration procedure.

Minimum historical training population per test year: `1000` matches.

---

## Serve/return matchup feature

For player A versus player B:

- estimate A service-point probability against B return,
- estimate B service-point probability against A return,
- define matchup edge as `p(A serve point) - p(B serve point)`.

The first experiment uses one symmetric matchup edge rather than a large collection of correlated serve statistics. Deeper first-serve, second-serve, ace, double-fault, break-point, and surface-conditioned decompositions remain future hypotheses.

---

## Primary metrics

1. Brier score — lower is better.
2. Binary log loss — lower is better.
3. 10-bin ECE diagnostic.
4. Accuracy — secondary/descriptive.

Primary comparison values are reported as baseline minus challenger for Brier/log loss, so positive values indicate improvement.

---

## Required slices

Report separately for ATP and WTA:

- aggregate common population,
- year-by-year performance,
- prior point-history thresholds based on the least-experienced side of the matchup:
  - `0+`
  - `250+`
  - `1000+`

The history threshold uses the minimum of both players' prior serve and return point exposure. A matchup is therefore treated as immature if any required side lacks historical point data.

---

## Adversarial checks

Before promotion:

1. Target-match stats cannot affect their own snapshot.
2. Same-date row order cannot affect snapshots.
3. Winner/loser source stats must be reoriented to canonical player A/B correctly.
4. Stats must remain absent from `PreMatchState`.
5. Stats artifacts must be separately hashed and manifest-verified.
6. Baseline and challenger must use identical future match IDs.
7. Standardization must fit on training years only.
8. Walkovers remain excluded.
9. Retirement sensitivity must remain separately labeled.
10. Inspect year-by-year reversals.
11. Inspect `250+` and `1000+` history slices so cold start cannot hide behind the aggregate.
12. Preserve this v1 configuration after the result is known.

---

## Pre-registered interpretation

### A / Core candidate

Promote when serve/return improves aggregate proper probability scores with broadly stable yearly behavior and the mature-history slices do not reverse the effect. Cross-tour replication materially strengthens an A classification.

### B / Conditional

Use when improvement is credible only on one tour or mainly once sufficient point history exists. The condition must be explicit; do not average it into a universal claim.

### C / Experimental

Retain when effects are tiny, unstable, or contradictory but suggest a better-specified follow-up such as surface-conditioned serve/return, decay, or stronger shrinkage.

### D / Rejected v1

Reject this formulation as a general addition when it worsens proper probability scores broadly, especially if the mature-history slices also fail.

A rejected v1 does not mean serve/return statistics contain no information. It means this exact registered transformation failed to extract stable incremental signal.

---

## Current entry point

```bash
python -m tennis_genome.experiments.exp003 \
  --manifest data/processed/atp_manifest.json \
  --pre-match data/processed/atp_pre_match.parquet \
  --outcomes data/processed/atp_outcomes.parquet \
  --stats data/processed/atp_stats.parquet \
  --min-train-matches 1000
```

Run ATP and WTA separately.

---

## Not yet claimed

At registration time, no real-data EXP-003 score has been accepted as a Tennis Genome finding. The pinned research workflow must complete successfully and the final standardized head must be audited before any promotion or rejection decision.
