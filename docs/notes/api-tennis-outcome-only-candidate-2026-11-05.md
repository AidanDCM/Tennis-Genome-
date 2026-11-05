# API-Tennis outcome-only candidate path

The retained-history bridge now has two separate research conversions:

- A complete, internally consistent enrichment can produce a candidate
  `HistoricalMatch` with point statistics.
- A normal finished row with an unambiguous winner can produce a candidate
  `HistoricalMatch` with `stats=None`, even if its statistics are missing or
  contradictory. Retirement, walkover, cancellation, missing winner and
  duplicate player keys are rejected.

Both conversions require a reviewed two-player canonical crosswalk, surface,
match format, source manifest hash, and a source observation before a target
on a later UTC calendar date. The outcome-only parser hashes the full raw row;
it does not copy, repair, or infer any point count. Neither conversion is wired
into the frozen production calculator or approved as a source.

As an offline smoke check, the receipt-verified November 4 API-Tennis backfill
(workflow run `42104561839`, two provider requests already made) contained 24
ATP/WTA singles rows. Twenty-three had a normal finished, unambiguous outcome.
Of these, 18 had complete internally consistent point statistics and five had
point-count conflicts. The new path keeps those five outcomes available for
later source review without treating their points as model input. These are
candidate counts, not an independent verification of the provider's winners.

Next: independently adjudicate outcome identity and tournament context,
reconcile duplicates with the pinned archive, then decide whether the
outcome-only rows may update ratings. Point-stat admission requires its own
source-quality evidence and must remain closed until that review passes.
