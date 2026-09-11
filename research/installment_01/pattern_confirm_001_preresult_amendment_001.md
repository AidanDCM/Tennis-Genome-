# PATTERN-CONFIRM-001 Pre-result Amendment 001 — Production Contracts

Status: **frozen while prospective N = 0 and before any eligible post-cutoff outcome is inspected**

This amendment hardens the transition from the historical research pipeline to live prospective operation. It does **not** change either hypothesis threshold, correction, family alpha, sequential boundary, look N, or promotion criterion.

## 1. Existing hypotheses remain unchanged

The family remains exactly:

1. `PC-ATP-PG-LOW`: `profile_gap < -0.4045998117259577`, frozen correction `-0.031143878674067826`.
2. `PC-ATP-PG-ABS-HIGH`: `abs(profile_gap) >= 0.47108555150900466`, frozen correction `-0.022734415112664306`.

The O'Brien-Fleming/Bonferroni design in `pattern_confirm.py` is unchanged.

## 2. Baseline-transfer compatibility audit

Before accepting the first prospective row, the already-spent 2023-2025 internal-validation matches are re-scored using the frozen pooled prospective Market+Core calibration in `pattern_confirm_001_market_core_fit.json`.

This is an engineering compatibility audit, not new confirmatory evidence. It may not inspect any post-cutoff prospective outcome.

The frozen corrections are retained without re-estimation only if, for each selected hypothesis:

- the recomputed residual has the same sign as the original internal-validation residual;
- the recomputed residual mean remains inside the original 2023-2025 bootstrap interval; and
- applying the already-frozen correction to the pooled baseline improves both Brier score and log loss on the already-spent block.

Failure would require a separate pre-prospective amendment before N can leave zero. It would not permit selecting a correction based on future data.

## 3. `PROFILE-PRODUCTION-001`

Future `profile_gap` values for this experiment must come from one frozen ATP strict Profile Strength mapping trained on eligible canonical ATP matches dated no later than 2025-12-31.

Frozen semantics:

- source snapshot: the same pinned 2000-2025 Sackmann archive used by PROFILE-GAP-001;
- tour: ATP;
- representation: strict (`include_conditional=False`);
- model class: `ProfileStrengthModel`;
- training population: eligible non-walkover, non-retirement ATP matches through 2025;
- dynamic state construction: the existing Player Profile v1 walk-forward implementation;
- state chronology: **date-level freeze semantics remain unchanged** — all matches on a calendar date see state from strictly earlier dates;
- fitted mapping coefficients/preprocessing are frozen for the full lifetime of PATTERN-CONFIRM-001;
- post-2025 outcomes may update only the legal dynamic player state for later dates; they may not refit the frozen Profile Strength mapping during this experiment.

The production artifact must include the exact feature order, imputer statistics, scaler parameters, model coefficients, Elo coordinate configuration, training-row provenance/hash, code-contract metadata, and a deterministic self-hash.

A same-day-aware or refitted Profile model is a future challenger, not a silent replacement.

## 4. `CORE-PRODUCTION-001`

Future `core_probability_a` values must come from one frozen ATP Strict Core mapping trained on the same eligible canonical ATP population through 2025.

Frozen semantics:

- feature set: `strict_a_features("ATP")` exactly;
- model class: `FeatureProbabilityModel`;
- fitted imputer, missingness indicators, scaler, logistic coefficients and intercept are frozen;
- dynamic FoundationalSnapshot state retains the existing date-level freeze semantics;
- post-2025 outcomes may update legal state for later dates but may not refit the Core mapping during PATTERN-CONFIRM-001.

The production artifact must include feature order, preprocessing state, model coefficients, training provenance/hash and a deterministic self-hash.

## 5. Prospective row model provenance

Every prospective input must identify the exact production artifacts that generated its upstream model values:

- `profile_model_sha256` must equal the frozen `PROFILE-PRODUCTION-001` artifact hash;
- `core_model_sha256` must equal the frozen `CORE-PRODUCTION-001` artifact hash;
- `market_core_fit_sha256` remains the existing frozen pooled Market+Core fit hash.

Rows with absent, mixed, or unexpected model hashes fail closed.

## 6. `LIVE-MARKET-V1` scientific benchmark

For PATTERN-CONFIRM-001, the scientific market benchmark is a two-sided Pinnacle ATP match-winner price observed prospectively.

Primary transport contract: `THE_ODDS_API_V4_PINNACLE_V1`, using bookmaker key `pinnacle` and the head-to-head/match-winner market. This transport choice does not authorize substitution by another bookmaker.

Rules:

- if a valid two-sided Pinnacle quote is unavailable, there is no confirmatory market row;
- both decimal prices must be finite and greater than 1;
- proportional two-way de-vigging is unchanged: `qA=1/oA`, `qB=1/oB`, `pA=qA/(qA+qB)`;
- no best-price, consensus, alternate-book, opening-price, or outcome-dependent fallback may rescue a missing confirmatory quote;
- other bookmaker prices may be stored separately for research/tradeability, but they do not replace the frozen scientific benchmark;
- provider/bookmaker quote timestamps and ingestion timestamps are mandatory;
- a quote older than 300 seconds at ingestion is not eligible for the confirmatory benchmark.

## 7. Five-minute pre-start market checkpoint

The intended scientific checkpoint is the latest otherwise-valid Pinnacle quote whose provider timestamp is at least five minutes before the provider's event start.

Because true first-serve time can differ from the pre-match schedule, logging and final eligibility are separated:

### Pre-match logging requirements

The prospective row must carry:

- `scheduled_start`;
- `provider_snapshot_at` (the bookmaker/provider quote timestamp);
- `ingested_at`;
- `prediction_generated_at`;
- `prediction_committed_at`;
- `market_provider`;
- `provider_event_id`;
- stable provider competitor IDs for both players;
- provider match state indicating that the event had not started when the quote was obtained.

The logger must require all timestamps to be timezone-aware and ordered so that the source snapshot is not from the future relative to ingestion, prediction is generated after ingestion, and prediction is committed before the then-known scheduled start.

### Post-match timing verification

Settlement must add a provider-derived `actual_start` for the same stable event ID. A row is confirmation-eligible only if:

- `provider_snapshot_at <= actual_start - 5 minutes`; and
- `prediction_committed_at < actual_start`.

Rows failing the final actual-start audit are retained as auditable timing exclusions and do not count toward any look N.

## 8. Identity contract

Confirmation rows require stable event and competitor identity from an approved tennis event feed. Market outcome names alone are insufficient identity.

The mapping contract is:

`market provider event/outcome -> approved event-provider event ID + competitor IDs -> canonical player IDs`

A row is eligible only when the orientation is unique and deterministic. Ambiguous identity, duplicate event mapping, or name-only unresolved identity fails closed. Name normalization may support QA but may not decide among multiple candidate identities using rankings, prices, signal values, outcomes, or performance.

The approved event-provider vendor may be connected later, but the above stable-ID semantics may not be weakened after prospective accumulation begins.

## 9. No prospective result has been spent

At the time of this amendment, both hypotheses remain `ACCUMULATING, N=0`. This amendment exists specifically so production semantics are fixed before the first eligible future result can enter the experiment.
