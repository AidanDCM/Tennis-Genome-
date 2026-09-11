# MARKET-BOOK-001 Amendment 003 — Outcome-Blind Tennis-Data Alias Resolution

Status: **PREREGISTERED / PRE-RESULT**

Date: 2026-09-11

## Trigger

Real-data MARKET-BOOK-QA-001 run `34612767772` completed the outcome-blind coverage gate without evaluating Profile Gap, Genome, Strict Core, MARKET-EDGE-001, or MARKET-EDGE-ADV-001. The gate returned `INSUFFICIENT_COVERAGE` and exposed a source-identity incompatibility in the preregistered Tennis-Data fallback.

The frozen source bundle contains 45,337 valid two-sided Tennis-Data Pinnacle quotes, but zero Tennis-Data rows resolved to the canonical Sackmann match history. Inspection of source identity fields showed the cause: Tennis-Data ordinarily encodes contestants as surname/compound-surname plus initials (for example `Dimitrov G.`, `De Minaur A.`, `Barrios Vera M.T.`), while the canonical history ordinarily stores full names (for example `Grigor Dimitrov`, `Alex De Minaur`, `Marcelo Tomas Barrios Vera`). The existing exact normalized-name resolver therefore cannot operationalize the already-preregistered Tennis-Data fallback.

The same QA run also showed that the Valuebetennis 2021 file contains no valid two-sided closing quotes, so a functioning lower-priority Tennis-Data fallback is necessary to test the originally frozen source hierarchy rather than silently testing Valuebetennis alone.

These observations are source-format and coverage-QA observations only. No signal-vs-market outcome or confirmatory edge result has been opened.

## Frozen resolver amendment

Exact normalized-name matching remains the first resolver path and remains unchanged.

Only when a `TENNIS_DATA_UK` quote has no exact pair match, each neutral Tennis-Data contestant may additionally resolve to a canonical contestant under the following deterministic alias rule.

### Abbreviated Tennis-Data form

A source name is treated as an abbreviated form when its final whitespace-delimited token either:

- contains a period; or
- after removing non-alphanumeric characters, is all uppercase alphabetic characters of length 1 through 3.

The final token is reduced to its alphabetic initials. The preceding source tokens form the normalized surname/compound-surname sequence.

A canonical full name matches that abbreviation only when:

1. the source surname tokens occur as a contiguous token sequence in the canonical normalized name after at least one canonical given-name token;
2. the source initials equal either:
   - the initials of all canonical tokens preceding the matched surname sequence; or
   - the first canonical given-name initial, allowing sources that omit secondary given-name initials;
3. compact canonical given-name tokens are also accepted when their letters exactly equal the source initials, allowing forms such as `Aragone JC` ↔ `JC Aragone`.

### Rare surname-first full form

For a two-token Tennis-Data name that is not classified as abbreviated, the resolver may also compare the reversed normalized token order. This supports deterministic source forms such as `Wang Xiyu` ↔ `Xiyu Wang`.

No broader fuzzy, edit-distance, phonetic, rank-based, odds-based, tournament-name, nationality, or manually curated outcome-informed matching is permitted.

## Candidate search and fail-closed behavior

The existing frozen tour and date-window semantics do not change. Alias resolution examines only canonical matches from the same tour whose canonical tournament-start date can satisfy:

```text
-4 <= source_match_date - canonical_event_date <= 21
```

For each candidate match, both neutral source contestants must map one-to-one onto the two canonical contestants. The odds orientation must therefore be unique.

- zero qualifying canonical matches -> `UNMATCHED`;
- exactly one qualifying match with exactly one contestant orientation -> `MATCHED`;
- more than one qualifying match, or non-unique contestant orientation -> `AMBIGUOUS`.

The resolver may not inspect winner identity, score, retirement, realized result, signal values, model probabilities, ranks, or the magnitude/direction of the quoted odds to break ambiguity.

## Versioning

Artifacts built under this amendment use a new resolver/batch version so they cannot be confused with the superseded exact-only artifact:

- resolver: `bookmaker-canonical-join-v2`;
- batch: `market-book-001-batch-v2`.

The MARKET-BOOK-QA structural validator must require those versions for the rerun.

## What remains frozen

This amendment does **not** change:

- `BOOKMAKER_CLOSE_V1` source priority: Valuebetennis first, Tennis-Data second;
- source files or their frozen hashes;
- valid-quote definition;
- the `-4/+21 day` identity window;
- duplicate/conflict handling;
- proportional two-way no-vig transform;
- ATP/WTA denominator definitions;
- 60% overall coverage threshold;
- 50% per-year 2021–2025 coverage threshold;
- 100-row recent-year threshold;
- 1,000 prior-row threshold;
- the four confirmatory claims;
- family alpha `.05`, family size `4`, or conservative planning alpha `.0125`;
- any Profile Gap, Genome, Strict Core, MARKET-EDGE, or MARKET-EDGE-ADV model or inference rule.

Run `34612767772` and its exact-only MARKET-BOOK artifact are superseded for confirmatory eligibility. If the corrected outcome-blind fallback still fails the originally frozen QA gates, the gates will not be lowered and confirmatory scoring will remain blocked.
