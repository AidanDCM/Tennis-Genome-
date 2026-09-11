# PATTERN-CONFIRM-001 Pre-result Amendment 003 — Provider Dry-run and Internal Signal Generation

Status: **frozen while prospective N = 0 and before any eligible post-cutoff outcome is inspected**

Amendments 001–002 froze the production mappings, Pinnacle scientific benchmark, identity authority, and actual-start authority. This amendment freezes the operational bridge from those contracts to real provider payloads. It does **not** change either selected hypothesis, frozen correction, family alpha, sequential boundary, look N, or promotion rule.

## 1. No externally injected scientific signals

A prospective row may not become confirmatory-eligible merely because a caller supplies numeric `profile_gap` and `core_probability_a` values alongside the correct artifact hashes.

Before prospective N can leave zero, the production path must internally reproduce both values from:

- the exact frozen `PROFILE-PRODUCTION-001` artifact;
- the exact frozen `CORE-PRODUCTION-001` artifact;
- a deterministic, hashed pre-match state artifact built only from legal information strictly before the target match/date; and
- the frozen date-level state semantics already used by the historical implementations.

The live envelope may store the resulting numbers, but the values must be reproducible from the sealed state/model inputs. Caller-supplied replacements are not authoritative.

## 2. Prospective state remains outcome-chronological

The fitted Profile and Core mappings remain frozen through the entire experiment. Post-2025 completed matches may update only the legal dynamic state used for later dates; they may not refit either mapping.

Any production state-update source used after 2025 must be frozen by exact source/version/hash before the first eligible prospective row. Until that source snapshot and its canonicalization contract are frozen, provider connectivity can be tested but the system is **not** `READY_FOR_ACCUMULATION`.

A target match may use only pre-match descriptive/context fields and state derived from strictly earlier completed dates. Target outcome, score, live point state, post-match statistics, and later-date information are forbidden.

## 3. Dry-run is transport/schema QA, not confirmation

`PATTERN-CONFIRM-PROVIDER-DRYRUN-001` is an outcome-blind operational audit. It may not:

- create a confirmatory prospective row;
- increment either hypothesis N;
- call the confirmation evaluator;
- inspect a target match outcome;
- request or parse Sportradar timelines/results for the candidate events;
- refit or tune any model, threshold, correction, mapping rule, or timing gate.

Dry-run output is therefore evidence that the real provider transports satisfy the frozen contracts, not evidence for or against either hypothesis.

## 4. The Odds API contract used by dry-run

Official v4 transport only:

- discover in-season sports with `GET /v4/sports/`;
- retain active Tennis sport keys only;
- request upcoming odds from `GET /v4/sports/{sport_key}/odds/`;
- bookmaker filter: `pinnacle` only;
- market: `h2h` only;
- odds format: decimal;
- no alternate bookmaker or best-price rescue.

For a candidate Pinnacle event, dry-run requires:

- stable The Odds API event ID;
- timezone-aware `commence_time`;
- bookmaker key exactly `pinnacle`;
- bookmaker `last_update` present and timezone-aware;
- exactly one `h2h` market;
- exactly two distinct named outcomes;
- finite decimal prices greater than 1;
- proportional two-way de-vig reproducible from those raw prices.

Credentials must be read only from environment/secrets and must never be serialized into reports, request logs, URLs, fixtures, or repository files.

## 5. Sportradar contract used by dry-run

Official Tennis v3 transport only. The dry-run uses future-date schedule/summary discovery plus the match-scoped Sport Event Summary for candidate revalidation. It must reuse the exact parser frozen in Amendment 002.

Only events satisfying all existing pre-match gates may become dry-run candidates:

- category `sr:category:3` / ATP;
- competition type `singles`;
- exactly one home and one away non-virtual competitor;
- `start_time_confirmed=true`;
- explicit admissible pre-match status (`not_started` or `scheduled`).

Dry-run discovery uses future UTC dates so the audit does not need completed-event result fields. The code must ignore any result/statistic fields even if a provider unexpectedly includes them.

## 6. Identity dry-run

The audit may attempt only the already-frozen exact-context identity path. It may use:

- exact normalized unordered competitor names;
- ATP/singles context;
- competition/tournament context;
- scheduled-time proximity.

It may not use fuzzy/edit-distance tie-breaking, rankings, odds, Profile/Core values, outcomes, or performance to choose among candidates.

Dry-run provider-to-provider alignment is descriptive QA. A real confirmatory row still requires canonical player IDs and a self-hashed `IdentityMapping` created before prediction commitment.

## 7. Readiness observations

A single HTTP success is not enough to declare the transports operationally ready.

A provider dry-run may report `TRANSPORT_COMPATIBLE` only after all of the following are observed:

1. both providers authenticate successfully and return parseable JSON;
2. at least one active Tennis sport key is discovered from The Odds API;
3. at least three distinct upcoming ATP singles events with valid two-sided Pinnacle `h2h` quotes are observed in total;
4. each of those events resolves uniquely to one admissible Sportradar ATP singles event using the frozen exact-context rules; and
5. the same event IDs/orientations remain stable across two snapshots separated by at least five minutes.

If fewer than three otherwise-valid events are available, the audit reports `INSUFFICIENT_LIVE_SAMPLE`, not failure. Schema/authentication/contract violations report `FAIL_CLOSED`.

`TRANSPORT_COMPATIBLE` still does **not** mean `READY_FOR_ACCUMULATION`; the internally reproducible live-state/signal path in Sections 1–2 must also be complete and frozen.

## 8. Dry-run provenance

Each dry-run report must be deterministic/self-hashed and record at minimum:

- run creation timestamp;
- provider contract versions;
- queried future UTC dates;
- discovered Tennis sport keys;
- counts of raw, Pinnacle-valid, Sportradar-admissible, uniquely aligned, and stable-across-snapshot events;
- per-candidate provider IDs, competitor names/IDs, scheduled times, bookmaker timestamp, raw odds, de-vigged probability, alignment status, and exclusion reason if any;
- elapsed time between snapshots;
- no API secrets.

Raw provider snapshots may be retained as private CI artifacts for debugging, but must never be committed to the repository and must not be used as confirmatory outcomes.

## 9. Current state

Both frozen hypotheses remain `ACCUMULATING, N=0`.

This amendment intentionally makes the next two gates explicit:

1. provider transports must pass outcome-blind dry-run QA; and
2. Profile/Core values must be internally reproduced from a frozen legal pre-match state path.

Only after both gates pass may the first prospective row be allowed to enter the confirmatory ledger.
