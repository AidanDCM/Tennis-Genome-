# MARKET-BOOK-001 Amendment 004 — Tennis-Data ISO Date Parser Correction

Status: **PREREGISTERED / PRE-RESULT**

Date: 2026-09-11

## Trigger

Outcome-blind MARKET-BOOK-QA-001 resolver-v2 run `34614993984` completed without evaluating Profile Gap, Genome, Strict Core, MARKET-EDGE-001, or MARKET-EDGE-ADV-001. ATP satisfied the frozen coverage gates; WTA did not. Before any signal scoring, an outcome-blind inspection of unmatched Tennis-Data source rows found a categorical date-sanitization defect.

A concrete raw source row in `wta_singles_results_2021.csv` has:

```text
Date = 2021-02-01
Winner = Cornet A.
Loser = Tomljanovic A.
```

The frozen raw row was sanitized by the current adapter as:

```text
match_date = 2021-01-02
```

The cause is implementation-level and source-format-specific: `_parse_tennis_data_date` passes `dayfirst=True` to `pandas.to_datetime` for every Tennis-Data date, including unambiguous ISO `YYYY-MM-DD` strings. Pandas warns about this exact condition, and for dates where both month and day are at most 12 it can reinterpret an ISO date as day-first and swap month/day.

This is a parser correctness defect independent of model signals, market-edge outcomes, or the numerical coverage threshold. No confirmatory signal-vs-market result has been opened.

## Frozen correction

Tennis-Data dates are parsed by format class:

1. If the stripped source value exactly matches `YYYY-MM-DD`, parse it as ISO using `date.fromisoformat`.
2. Otherwise, retain the previously registered legacy day-first parser (`dayfirst=True`) for historical non-ISO Tennis-Data forms such as `3/2/21`.
3. Malformed dates continue to fail closed.

No date is inferred from tournament name, player identity, result, score, odds, canonical match date, or any other row.

## Versioning

Because corrected dates change sanitized row hashes and downstream joins, corrected artifacts must be distinguishable from the superseded run:

- neutralization version: `bookmaker-neutralization-v2`;
- batch version: `market-book-001-batch-v3`;
- identity resolver remains `bookmaker-canonical-join-v2` because Amendment 003 identity rules are unchanged.

MARKET-BOOK-QA structural validation for the corrected rerun must require batch v3 and resolver v2.

## What remains frozen

This amendment does **not** change:

- the source files or their byte hashes;
- Valuebetennis parsing;
- Tennis-Data Pinnacle fields `PSW` / `PSL`;
- outcome neutralization;
- the Amendment 003 alias resolver;
- the `-4/+21 day` join window;
- `BOOKMAKER_CLOSE_V1` source priority;
- duplicate/conflict behavior;
- proportional two-way no-vig transform;
- ATP/WTA denominator definitions;
- 60% overall coverage threshold;
- 50% per-year 2021–2025 coverage threshold;
- 100-row recent-year threshold;
- 1,000 prior-row threshold;
- the four confirmatory claims;
- family alpha `.05`, family size `4`, or conservative planning alpha `.0125`;
- any Profile Gap, Genome, Strict Core, MARKET-EDGE, or MARKET-EDGE-ADV model or inference rule.

Runs using the pre-correction Tennis-Data date parser are superseded for confirmatory eligibility. The corrected outcome-blind QA gates remain authoritative. If they fail, the thresholds will not be lowered and confirmatory scoring remains blocked.
