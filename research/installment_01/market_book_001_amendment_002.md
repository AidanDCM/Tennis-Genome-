# MARKET-BOOK-001 Amendment 002 — Indexed Canonical Identity Resolution

Status: **PREREGISTERED / PRE-RESULT**

Date: 2026-09-11

## Trigger

During the first real-data execution, before any Profile Gap, Genome, Strict Core, MARKET-EDGE, or MARKET-EDGE-ADV result was opened, the implementation was audited for real-source runtime behavior.

The original canonical resolver evaluated every sanitized bookmaker quote by scanning every canonical pre-match state. That implementation is semantically correct on small synthetic fixtures but scales as approximately `O(number_of_quotes × number_of_canonical_matches)`. With the frozen real source bundle this implies tens of billions of unnecessary pair comparisons and makes the confirmatory construction operationally impractical.

## Implementation clarification

Canonical pre-match states are now indexed once by the exact preregistered identity key:

```text
(tour, sorted(normalize(player_a_name), normalize(player_b_name)))
```

For each bookmaker quote, the resolver examines only canonical states in that exact bucket, then applies the unchanged frozen date-offset rule:

```text
-4 <= source_match_date - canonical_event_date <= 21 days
```

Candidate handling remains unchanged:

- zero qualifying candidates -> `UNMATCHED`;
- exactly one -> `MATCHED`;
- more than one -> `AMBIGUOUS`.

Canonical A/B orientation, join hashes, source priority, duplicate/conflict handling, and no-vig price construction are unchanged.

## Methodology impact

None. This amendment changes lookup complexity only. It does not alter:

- the normalization function;
- unordered player-pair semantics;
- tour matching;
- date window;
- ambiguity rules;
- source hierarchy;
- closing-price definitions;
- QA thresholds;
- confirmatory claims;
- statistical models or inference.

A regression explicitly verifies that two canonical matches sharing the same normalized pair and both inside the frozen date window remain `AMBIGUOUS` after indexing.

This optimization was made before confirmatory market-performance results were observed.
