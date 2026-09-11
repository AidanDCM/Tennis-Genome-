# MARKET-BOOK-001 — Outcome-Blind Bookmaker Closing-Market Artifact

Status: **PREREGISTERED / PRE-RESULT**

## Purpose

Construct a deterministic, outcome-free historical market artifact for the frozen MARKET-EDGE information-overlap tests when Betfair Historical Data is not operationally available.

MARKET-BOOK-001 is an ingestion and identity-resolution experiment. It does not inspect Profile Gap or Genome performance and it does not establish edge, expected value, ROI, CLV, or profitability.

## Frozen source hierarchy

Primary quote policy: `BOOKMAKER_CLOSE_V1`.

For each canonical match:

1. use a valid two-sided Valuebetennis closing quote when available;
2. otherwise use a valid two-sided Tennis-Data Pinnacle `PSW`/`PSL` quote;
3. otherwise emit no usable primary market quote for that match.

A valid decimal quote is finite and strictly greater than 1.0 on both sides.

The hierarchy is deterministic. A lower-priority source may never replace a valid higher-priority quote based on price level, signal direction, outcome, model score, or later performance.

## Confirmatory time boundary

The confirmatory artifact may contain source rows dated no later than `2025-12-31`. Any 2026-or-later source row is rejected from confirmatory construction.

Pre-2021 history is retained for chronological model fitting and the frozen `min_prior_rows=1000` gate.

## Outcome firewall

### Valuebetennis

Only source identity/date/tour fields and `cote1_cloture`/`cote2_cloture` may influence emitted market records.

Fields including `vainqueur_id`, `score`, and `duree_min` are result/post-match data. They may exist in the raw source file but must not appear in sanitized market records and may not influence quote eligibility, identity matching, source priority, or probability construction.

### Tennis-Data

The source stores contestants under outcome-bearing `Winner`/`Loser` labels. Neutralization therefore occurs inside the source adapter before any downstream join or analysis:

1. normalize each contestant name with the frozen market-name normalizer;
2. lexicographically sort the two normalized names;
3. carry the corresponding `PSW` or `PSL` decimal price with its contestant into that neutral order;
4. discard the raw Winner/Loser role after the neutral record is formed;
5. do not emit score, sets, result comment, or any other outcome/post-match column.

Downstream MARKET-BOOK code receives only neutral contestant slots.

## Identity resolver

The bookmaker resolver uses the existing canonical market-name normalization and unordered exact player-pair matching.

Because canonical `event_date` currently represents tournament start rather than exact match date, a candidate canonical match must fall within the already-frozen market identity window relative to the source match date:

- canonical tournament start may be at most 4 days after the source match date;
- source match date may be at most 21 days after canonical tournament start.

Equivalent offset rule, where `offset = source_match_date - canonical_event_date`:

```text
-4 <= offset_days <= 21
```

Zero candidates -> `UNMATCHED`.

More than one candidate -> `AMBIGUOUS`.

Exactly one candidate -> `MATCHED` and oriented into canonical A/B by normalized player name.

No manual outcome-informed candidate selection is allowed.

## Probability transform

For the selected two-sided quote, compute the primary market probability with the repository's existing proportional two-way no-vig transform:

```text
q_a = 1 / odds_a
q_b = 1 / odds_b
p_a = q_a / (q_a + q_b)
p_b = q_b / (q_a + q_b)
```

Store raw decimal odds, raw implied-probability sum/overround, and no-vig probabilities.

## Duplicate and overlap handling

Multiple source rows that resolve to the same canonical match are handled without outcomes:

- first collapse exact duplicate sanitized rows deterministically;
- within one source, conflicting valid quotes for one canonical match are not averaged or cherry-picked: the match is marked source-conflicted and that source cannot provide the primary quote;
- across sources, the frozen hierarchy applies only after each source has at most one valid quote for the canonical match;
- when both valid source quotes exist, retain both for overlap diagnostics but mark only Valuebetennis as `selected_primary=true`.

This fail-closed rule prevents accidental row-order dependence.

## Required record provenance

Each sanitized source quote and each canonical market record must retain enough non-outcome provenance to reproduce it:

- source name;
- relative source path;
- source file SHA-256;
- deterministic sanitized-row hash;
- source match date;
- neutral source contestant names;
- raw selected decimal odds;
- identity status and candidate canonical match IDs;
- join hash when matched;
- selected source under `BOOKMAKER_CLOSE_V1`;
- no-vig probabilities and overround;
- deterministic record hash.

Raw source files remain outside Git.

## Determinism

Given the same source files, canonical pre-match table, hierarchy, date window, and no-vig transform, two runs must produce byte-equivalent canonical record ordering and the same aggregate output SHA-256.

## Explicit exclusions

MARKET-BOOK-001 does not create or infer:

- exchange back/lay prices;
- executable liquidity or fill size;
- Betfair commission;
- T-24H, T-6H, T-1H, or T-15M checkpoints;
- historical CLV;
- realized betting P&L;
- a betting policy.

Those require a separate future source and preregistration.
