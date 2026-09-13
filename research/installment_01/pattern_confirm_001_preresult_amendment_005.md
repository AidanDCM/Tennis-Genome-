# PATTERN-CONFIRM-001 Pre-result Amendment 005 — Sportradar Context and State Adapter Semantics

Status: **frozen while prospective N = 0 and before any eligible post-cutoff outcome is inspected**

Amendment 004 requires a deterministic target-context adapter and a frozen post-2025 dynamic-state source before `READY_FOR_ACCUMULATION`. This amendment freezes the exact translation rules used by those adapters before implementation.

No selected hypothesis, correction, family alpha, O'Brien-Fleming boundary, look N, or promotion rule changes.

## 1. Source contracts

The target pre-match context uses only pre-match Sportradar Tennis v3 data:

- Sport Event Summary for stable event/competition/season/round/mode/competitor orientation and seed;
- Season Info for surface and competition level;
- Competitor Profile for date of birth, height, handedness and country code.

The post-2025 dynamic-state extension uses completed ATP singles Sport Event Summary / Season Summaries records under source contract `SPORTRADAR_TENNIS_V3_STATE_V1`.

Provider response bodies used by either adapter are content-hashed. API keys, authorization headers and URLs containing credentials are never included in artifacts.

## 2. Target canonical event date

The target `PreMatchState.event_date` remains the already-frozen Sportradar `season.start_date` from Amendment 004. The target identity mapping's season ID, season start date, competition ID, event ID and competitor orientation must agree with the fresh source objects.

## 3. Surface mapping

Surface strings are normalized only by trimming, lowercasing, and replacing spaces/hyphens with underscores. The frozen accepted mapping is:

- `hardcourt_outdoor`, `hardcourt_indoor`, `hard_court`, `hardcourt`, `hard` -> `Hard`
- `red_clay`, `green_clay`, `clay` -> `Clay`
- `grass` -> `Grass`
- `carpet_indoor`, `carpet` -> `Carpet`
- missing/blank or explicit `unknown` -> canonical `Unknown`

A different non-empty surface value fails closed. In particular, synthetic surfaces are not silently collapsed into a historical surface family.

## 4. Competition-level mapping

The accepted ATP competition-level mapping is:

- `grand_slam` -> historical `G`
- `atp_1000` -> historical `M`
- `atp_world_tour_finals` -> historical `F`
- `atp_500`, `atp_250`, `atp_next_generation` -> historical `A`
- missing/blank -> `None`

Any other non-empty level fails closed for PATTERN-CONFIRM-001. Challenger, Davis Cup, exhibition and other categories are already outside the frozen ATP-category contract and cannot be rescued by level recoding.

## 5. Round mapping

The frozen round-name mapping is:

- `round_of_256` -> `R256`
- `round_of_128` -> `R128`
- `round_of_64` -> `R64`
- `round_of_32` -> `R32`
- `round_of_16` -> `R16`
- `quarterfinal` -> `QF`
- `semifinal` -> `SF`
- `final` -> `F`
- `qualification` -> `Q`
- `qualification_final` -> `QFNL`
- `qualification_round_1` -> `Q1`
- `qualification_round_2` -> `Q2`
- `round_1` -> `R1`
- `round_2` -> `R2`
- `round_3` -> `R3`

Missing round remains `None`. Any other non-empty round value fails closed rather than being guessed. This is intentionally conservative; a future amendment may add a provider enum only before that newly encountered value contributes to a prospective row.

## 6. Best-of, seed, entry and rankings

`best_of` is read only from `sport_event_context.mode.best_of` and must be a positive integer when present. Seed is read from the correctly oriented Sportradar competitor and must be a positive integer when present.

The currently documented Tennis v3 Summary/Profile fields do not provide a frozen, target-time entry-path field equivalent to Sackmann `Q/WC/LL/PR`. Therefore `entry_a` and `entry_b` are `None`; they may not be inferred from names, bracket positions, rankings or later results.

Target `rank_*` and `rank_points_*` remain `None` because neither frozen production model uses them and a later ranking snapshot may not be backfilled. This avoids introducing a new ranking-timestamp contract solely for unused fields.

## 7. Competitor demographics

Competitor Profile must reproduce the expected Sportradar competitor ID. `date_of_birth`, when present, is converted to age on the frozen season start date using exact elapsed days divided by `365.25`. Future birth dates fail closed.

Handedness maps only `right` -> `R`, `left` -> `L`; blank/missing -> `None`; any other non-empty value fails closed. Height is centimeters and must be a positive integer when present. Country code is carried as published or `None` when missing.

## 8. Completed state-row eligibility

A state-extension match is admitted only when all of the following are true:

- category is exactly ATP (`sr:category:3`);
- competition type is `singles`;
- season ID/start date and competition ID are present and internally consistent;
- both stable competitor IDs resolve uniquely through the sealed Sportradar-to-canonical crosswalk;
- event status is `ended` or `closed`;
- `winner_id` equals exactly one of the two competitors.

`walkover`, `retirement`, and `defaulted` are retained in the source audit but excluded from legal dynamic-state updates. `defaulted` is conservatively treated as an exclusion rather than a normal completed match.

No score, market price or model output participates in identity resolution.

## 9. State statistics

For an admitted normal completion, `service_points` is derived exactly as:

`service_points_won + service_points_lost`

for each side when both fields are present. First- and second-serve points won are carried directly. If direct `service_points_won` and the sum of `first_serve_points_won + second_serve_points_won` are all present, they must agree or the match fails closed as structurally inconsistent.

Aces and double faults may be retained when available. Match duration is `None` unless a separately frozen, verifiable duration source is later added; missing duration is never imputed to zero.

Missing point statistics remain missing and therefore cannot update point-strength state for that match. They do not receive inferred values from scores or other matches.

## 10. Source bundle sealing

The post-2025 state bundle stores:

- source contract/version;
- canonical crosswalk SHA-256;
- raw provider-body SHA-256 over deterministic canonicalized source objects;
- parsed-row SHA-256;
- accepted/excluded counts with exclusion reasons;
- maximum included canonical event date;
- deterministic artifact self-hash.

Before any target state is generated for confirmation, its `history_source_sha256` must point to a verified sealed state bundle whose rows all have canonical event dates strictly earlier than the target season start date.

## 11. Readiness remains fail-closed

Implementation and synthetic tests of these adapters do not by themselves make the experiment ready. `READY_FOR_ACCUMULATION` still requires a real credentialed no-outcome provider dry-run and a real sealed post-2025 state bundle. Until those occur, both hypotheses remain `ACCUMULATING, N=0`.
