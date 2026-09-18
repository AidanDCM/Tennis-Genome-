# API-Tennis conservative WTA serve/return shadow 001

Status: **frozen development-derived shadow challenger; not Champion; not independent confirmation**

## Purpose

Freeze the next API-Tennis dynamic serve/return challenger before prospective scoring. This
candidate exists because the raw dynamic PointSim probability was overconfident in the retained
31-day development replay, while a conservative WTA history-gated transformation was materially
better behaved.

This document is a governance freeze, not a promotion claim.

## Frozen rule

The challenger ID is:

`TGE-CHALLENGER-WTA-DYNAMIC-SR-SHRUNK-V1`

For one pre-match dynamic API-Tennis record:

1. Require `tour == WTA`.
2. Define each player's prior history as:
   `prior_serve_points + prior_return_points`.
3. Require **both players** to have at least **200 combined prior points**.
4. Let `p_raw` be the already-frozen dynamic serve/return PointSim match probability.
5. Shrink **80% of the distance to neutral**:
   `p_shadow = 0.50 + 0.20 * (p_raw - 0.50)`.
6. If the match is ineligible, **abstain**. Do not emit a 0.50 pseudo-prediction.

The threshold and shrinkage are fixed. They must not be changed after inspecting prospective
outcomes. A different threshold, tour policy, state model, or shrinkage amount is a new challenger
with a new ID.

## Development evidence that motivated the freeze

The 31-day retained API-Tennis replay contained 728 ATP/WTA singles fixtures and 686 usable
matches. The raw dynamic challenger was overconfident overall. The development diagnostic for
WTA matches where both players had at least 200 combined prior serve/return points produced
104 matches, 57.7% directional accuracy, Brier 0.2444, and log loss 0.6819 after 80% shrinkage
toward 0.50.

Those figures are **development-only**. They are not independent forward evidence and cannot
justify Champion promotion.

## Prospective-shadow boundary

Implementation returns a standard `ShadowModelOutput`, so eligible predictions can be bound to
the repository's existing immutable `CommonPreMatchSnapshot` / `ShadowPredictionRecord` lane
and externally anchored before scheduled start.

The challenger consumes no bookmaker, odds, market, outcome, staking, profit, or settlement
information at prediction time. Post-result scoring stays in the existing settlement path.

## Promotion boundary

No Champion behavior changes in this work. Promotion requires a separately declared prospective
sample and promotion contract. Prospective outcomes may evaluate this exact frozen rule; they may
not be used to retune it and then counted as confirmation.

## Provider-use boundary

Implementing and replaying this challenger from already-retained artifacts requires **zero**
additional API-Tennis requests.
