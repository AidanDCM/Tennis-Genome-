# MARKET-EDGE-001 — Pre-Result Amendment 005

Status: **FROZEN BEFORE LICENSED BETFAIR MARKET RESULTS**

## Purpose

Prevent tennis retirement settlement semantics from contaminating the primary market-incrementality experiment.

## Primary population change

The primary MARKET-EDGE-001 proper-score population includes only canonical matches that are:

- not walkovers; and
- not retirements.

The canonical outcome table remains the result source for these completed matches.

## Rationale

Betfair tennis Match Odds settlement can depend on competition type and the point in the match at which a player retires or is disqualified. A canonical tennis winner/progression flag therefore cannot be assumed to equal the settled Exchange outcome for every retirement.

Until Tennis Genome reconstructs explicit Betfair settlement state and, where needed, historical settlement-rule context, retirement rows are not eligible for the confirmatory Brier/log-loss market-incrementality claims.

This is deliberately conservative: removing retirement rows may reduce sample size, but it prevents a settlement-rule mismatch from being mistaken for prediction error or market edge.

## Future retirement analysis

A later settlement-aware market study may include retirements only when the data layer can establish the actual Exchange settlement/void state for the specific market. That future study must be registered separately and cannot retroactively alter MARKET-EDGE-001.

## Unchanged

This amendment does not change:

- the four ATP/WTA × Profile Gap/Genome claims;
- the closing-market probability transform;
- the chronological market-recalibration control;
- bootstrap/permutation/McNemar procedures;
- Holm correction;
- year/recent/concentration gates;
- Profile Gap or Genome definitions;
- the post-2025 prohibition;
- commission/CLV diagnostics;
- TGE-Independent-v1;
- the non-claim of profitability.
