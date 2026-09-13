# Matchup Calculator v1

Status: **development implementation on top of the frozen TGE-Independent-v1 production bundle**.

## Purpose

The matchup calculator is a market-blind fair-probability engine. Given legal pre-match state for two players, it produces:

- fair Player A / Player B win probabilities;
- model-derived fair decimal odds as a presentation transform;
- frozen component probabilities;
- historical-neighbor support and distance diagnostics;
- the tour-specific uncertainty diagnostic retained by TGE-Independent-v1;
- source/provenance hashes;
- an explicit diagnostic-only assessment status.

It does **not** state that a player will win, recommend a bet, ingest sportsbook prices, or create a hard PASS/PREDICT decision.

## Provider-neutral input

`MatchupInput` is deliberately independent of Sportradar, The Odds API, or any other live provider. A caller may construct the same input from a future provider adapter, a validated offline state capture, or another source that satisfies the pre-match information contract.

Common input state:

- immutable prediction and match IDs;
- tour and canonical Player A / Player B IDs;
- timezone-aware creation and information-cutoff timestamps;
- pre-match `FoundationalSnapshot`;
- source manifest SHA-256 values;
- match format (`best_of`).

ATP additionally requires the pre-match `MatchProfilePair` used by the full Profile-aware Genome representation.

WTA additionally requires the pre-match `ServeReturnSnapshot` used to generate the raw PointSim mechanical input. That raw PointSim probability is not a standalone forecast; it enters only through the frozen two-input WTA meta mapping.

## Frozen ATP inference

1. Evaluate the frozen terminal `strict_core_v1` mapping.
2. Canonicalize the target toward the Elo-favored orientation.
3. Build the accepted full Profile-aware Genome vector.
4. Query the frozen historical residual/vector bank at k=100.
5. Apply the frozen alignment mapping to `logit(Core favorite probability)` plus the mean k=100 neighbor residual.
6. Transform the favorite-oriented result back to Player A orientation.
7. Apply identity calibration (no additional transform).

Diagnostics include Core confidence, the registered conditioned Genome unfamiliarity z-score, neighbor pool/support distances, vector missing fraction, and player-history depth. No diagnostic is converted into a hard PASS threshold.

## Frozen WTA inference

1. Evaluate the frozen terminal `strict_core_v1` mapping.
2. Build the canonical strict-Core geometry target vector.
3. Query the frozen historical residual/vector bank at k=100.
4. Apply the frozen historical-alignment mapping.
5. Compute raw PointSim probability from the pre-match serve-point state and match format.
6. Apply the frozen WTA two-input mapping over `logit(alignment probability)` and `logit(PointSim probability)`.
7. Apply identity calibration (no additional transform).

The retained WTA disagreement diagnostic preserves the historical CAL-SEL definition:

`max(Elo-only, strict Core, A+B) - min(Elo-only, strict Core, A+B)`

Raw PointSim remains a conditional component only.

## Historical-neighbor chronology

The calculator filters the frozen bank to records with `event_date < target.event_date` before constructing `HistoricalGenomeIndex`. The reusable index then independently rejects self, same-day, or future candidates before fitting imputation/scaling.

The terminal production bundle itself was fit on the complete accepted 2000-2025 development population. Therefore this calculator **refuses targets dated 2025 or earlier**. Using the terminal fit to replay its own development period would leak future training information through the fitted Core/meta parameters even if the neighbor bank were date-filtered.

A truthful historical replay mode requires a separate chronological replay engine using only models/state fit strictly before each replay target. That is a separate development task; the production calculator does not pretend otherwise.

## Fair decimal odds

Fair decimal odds are a deterministic display transform of the independent probabilities:

`fair_decimal = 1 / probability`

They are stored in `MatchupCalculation`, not inside `IndependentPrediction`. This preserves the frozen independent-prediction firewall, whose schema rejects fields containing odds/market/edge/EV semantics.

Fair odds are **not sportsbook odds** and do not imply positive expected value.

## Market comparison remains downstream

If a user manually supplies sportsbook prices later, they must enter the existing separate market layer:

`IndependentPrediction -> MarketSnapshot -> compare_prediction_to_market(...)`

That layer may calculate proportional two-way no-vig probabilities, edge in percentage points, and expected value per unit. Market information must never flow backward into the calculator or TGE-Independent-v1 state.

## Assessment semantics

Every v1 calculation reports:

`DIAGNOSTIC_ONLY_NO_HARD_PASS`

and the independent prediction carries `NO_HARD_PASS_POLICY`.

This is descriptive, not an abstention rule. The frozen architecture explicitly has no promoted hard PASS/PREDICT threshold.

## Non-claims

The calculator is not evidence of:

- deterministic match prediction;
- independent forward confirmation of every late-added component;
- sportsbook edge;
- positive expected value;
- profitability;
- permission for real-money deployment.

Those require separate prospective evidence and downstream decision-policy validation.
