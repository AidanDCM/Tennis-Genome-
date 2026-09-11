# PATTERN-CONFIRM-001 Live Contract Findings

Status: **PRE-LIVE HARDENING COMPLETE; PROSPECTIVE N = 0**

This record summarizes the production/live engineering completed before the first eligible post-cutoff result can enter `PATTERN-CONFIRM-001`.

No post-cutoff outcome was inspected while implementing or testing these contracts. No hypothesis threshold, correction, family alpha, O'Brien-Fleming boundary, look N, or promotion rule changed.

## Baseline transfer decision

The spent 2023-2025 validation block was re-scored under the frozen pooled prospective Market+Core baseline. Both selected regimes preserved direction, remained inside their original bootstrap intervals, and retained positive Brier and log-loss improvement under the already-frozen correction.

Therefore the original corrections remain unchanged. See:

- `pattern_confirm_001_baseline_transfer_audit.json`
- `pattern_confirm_001_baseline_transfer_findings.md`

## Frozen upstream production mappings

- `PROFILE-PRODUCTION-001` artifact SHA-256: `cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351`
- `CORE-PRODUCTION-001` artifact SHA-256: `5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7`
- common eligible ATP training N: `75,112`
- common training-row SHA-256: `c2c5b4ddcd30f68d75b98a9b5e460ff71d4601b50115695bb1784c8f5f897d2c`
- training cutoff: 2025-12-31
- dynamic state semantics: `strictly-earlier-date-state-v1`

Post-2025 completed matches may legally update dynamic state for later dates but may not refit either frozen mapping during this experiment.

## Market contract

Scientific benchmark:

- transport: `THE_ODDS_API_V4_PINNACLE_V1`
- bookmaker: Pinnacle
- market: ATP singles two-sided head-to-head / match winner
- valid decimal odds: finite and greater than 1 on both sides
- market probability: proportional two-way de-vig only
- missing Pinnacle quote: no confirmatory row
- no alternate bookmaker, consensus, best-price, opening-price, or outcome-dependent rescue
- quote staleness at ingestion: maximum 300 seconds

## Stable identity contract

Event authority: `SPORTRADAR_TENNIS_V3`.

Every live row must be linked through a deterministic, self-hashed identity artifact:

`The Odds API event -> Sportradar sport-event + competitor IDs -> canonical player IDs`

The approved mapping methods are:

- `EXPLICIT_CROSSWALK`
- `EXACT_CONTEXT_UNIQUE`
- `MANUAL_PREMATCH`

The automated exact-context path may use only exact normalized unordered competitor names, ATP/singles context, competition context, and scheduled-time proximity. It may resolve only when exactly one event/orientation remains. Fuzzy/edit-distance tie-breaking and ranking, odds, Profile/Core, outcome, or performance information are forbidden for identity resolution.

The mapping must be created before the scheduled start, and a fresh Sportradar pre-match summary must still agree with the sealed event ID, competitor orientation, competition and scheduled start when the prospective prediction is committed.

## Actual-start contract

The pre-match Sportradar event must:

- be category `sr:category:3` / ATP;
- be a `singles` competition;
- have exactly one home and one away non-virtual competitor;
- have `start_time_confirmed=true`;
- provide an explicit admissible pre-match status (`not_started` or `scheduled`); a missing status fails closed;
- not already be live, ended, closed, cancelled, abandoned, interrupted, suspended or postponed.

Final actual start is **not** the schedule. It is the earliest `match_started` event in the Sportradar sport-event timeline for the same stable sport-event ID.

If no `match_started` event exists, the row is retained as an auditable exclusion with reason `ACTUAL_START_UNVERIFIED` and contributes zero to confirmatory N. No scheduled-start, first-score, settlement-time or bookmaker-market-close fallback is allowed.

A settled row is timing-eligible only when:

- the Pinnacle provider snapshot is at least five minutes before verified actual start; and
- `prediction_committed_at` is strictly before verified actual start.

Settlement `retirement`, `walkover`, and non-null `outcome_a` values must be real JSON booleans. String/numeric truthiness is rejected rather than coerced.

## Live ledger hardening

`pattern_confirm_live.py` version `pattern-confirm-live-v2` now requires a verified identity mapping rather than trusting a free-form mapping hash.

The sealed row binds:

- market event ID;
- Sportradar event ID;
- market player orientation;
- Sportradar competitor IDs;
- canonical player IDs;
- identity mapping hash;
- fresh Sportradar summary hash;
- raw two-sided Pinnacle decimal odds;
- de-vigged market probability;
- provider snapshot, ingestion, generation and commitment timestamps;
- Profile production artifact hash;
- Core production artifact hash;
- frozen Market+Core fit hash;
- nested frozen confirmation-engine record;
- source-row hash and live-record self-hash.

Loading an existing sealed ledger revalidates semantic invariants rather than trusting the self-hash alone. A row that is altered and then rehashed still fails if its provider/source, player/event mapping, state, timing, raw odds, de-vigged probability or model provenance violates the frozen contract.

The runtime also hard-pins the exact preregistered champion artifact identities. Supplying a different but internally valid/rehashed artifact cannot redefine the experiment:

- Profile artifact SHA-256: `cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351`
- Core artifact SHA-256: `5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7`
- Market+Core fit SHA-256: `622d07e4a5d010b927ddf1c37900868a61d2e81d67c287f2a41dddaf4932b732`

Changing any of these three champion artifacts requires a new explicitly versioned experiment rather than an in-place substitution.

## Verification execution

Core semantic hardening commit:

- `e7088fcc92107410738df3e2143a38fa087880b4`
- message: `Reverify sealed live identity and timing semantics`

One-shot integrity workflow:

- workflow run: `34651542674`
- job: `103434602760`
- patch step: success
- full `ruff check .`: success
- full `pytest`: success
- commit step: success

Immediately before that semantic patch, normal CI on the integrated identity/timeline implementation reported **371 tests passed**; its only failure was a Ruff import-modernization rule, which the hardening run corrected before committing `e7088fcc...`.

Final input hardening then added explicit provider-status enforcement, strict JSON settlement booleans, and exact runtime pinning of all three champion artifact hashes. The one-shot full-suite hardening workflows completed successfully before those commits were accepted on the branch.

## Current scientific state

Both frozen hypotheses remain `ACCUMULATING, N=0`.

The system is structurally ready for a real provider-connected prospective row only after the branch itself passes final normal CI and is merged. Connecting credentials or beginning live accumulation is a separate operational action; it has not occurred here.
