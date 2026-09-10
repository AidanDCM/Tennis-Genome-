# PROFILE-GAP-001 Pre-result Amendment 001

Status: **frozen before any PROFILE-GAP-001 result is inspected**

This amendment resolves implementation details left underspecified in `profile_gap_protocol.md`. It does not change the feature set, model family, source, holdout policy, or promotion gate.

## Gap quintiles

Gap quintiles are equal-count rank buckets over the complete out-of-sample prediction population for the reported period.

Procedure:
1. sort by `profile_gap_match` ascending;
2. break exact numerical ties by `match_id` ascending;
3. assign bucket `1 + floor(rank * 5 / N)`, capped at 5.

Quintile 1 is the most Elo-negative Profile Gap and quintile 5 the most Elo-positive.

The 2021–2025 diagnostic recomputes quintiles inside the 2021–2025 subset rather than reusing full-history cut points.

## Data-depth thresholds

The minimum-prior-match diagnostic reports nested slices at:
- `>= 0`
- `>= 10`
- `>= 25`
- `>= 50`

where the match value is `min(player_a.prior_matches, player_b.prior_matches)`.

For experiments whose registered profile representation includes serve/return, minimum point-history slices are:
- `>= 0`
- `>= 250`
- `>= 1000`

where the match value is the minimum of both players' prior serve and return point counts. These thresholds intentionally reuse the earlier EXP-003 history-depth convention rather than being selected from PROFILE-GAP-001 results.

Duration coverage is reported as exactly two descriptive groups:
- both players have complete 14-day duration history;
- at least one player has incomplete 14-day duration history.

No threshold in this amendment may become a PASS/betting rule from PROFILE-GAP-001 itself.

## Year-win counting

A year counts as a Profile Strength win only when **both**:
- Profile Brier < Elo Brier; and
- Profile log loss < Elo log loss.

Ties are not wins.

The registered 60% yearly-win promotion condition uses this joint definition.

## Recent block

The recent-regime block remains calendar years **2021–2025 inclusive**. If a future implementation is run on a shorter dataset, the recent block must be reported as unavailable rather than silently changing the years.

## Strict Core benchmark alignment

Strict Core v1 is fit and evaluated on the same outer test years and target matches used by Profile Strength wherever its foundational snapshot exists. Core preprocessing/model fitting uses training years only, exactly as in the existing `FeatureProbabilityModel` implementation.

The Profile-vs-Elo comparison remains the primary H-009 test. Strict Core is contextual benchmarking and cannot redefine Profile Gap.
