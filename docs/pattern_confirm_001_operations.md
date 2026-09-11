# PATTERN-CONFIRM-001 operations

This runbook is deliberately boring. The research design is already frozen; operations must preserve it rather than optimize it after future results appear.

## Current state

- Prospective cutoff: `2026-09-12T00:00:00-04:00`
- Frozen baseline: `research/installment_01/pattern_confirm_001_market_core_fit.json`
- Status at setup: `ACCUMULATING`, N=0 for both hypotheses
- No pre-cutoff 2026 match is eligible for independent confirmation.

## Pre-match batch schema

Each row presented to the logger is JSONL with exactly the information needed to construct an outcome-free prospective record. Example:

```json
{"match_id":"canonical-id","tour":"ATP","scheduled_start":"2026-09-12T14:00:00-04:00","observed_at":"2026-09-12T13:55:00-04:00","market_source":"BOOKMAKER_CLOSE_V1","market_probability_a":0.58,"core_probability_a":0.55,"profile_gap":-0.60}
```

The confirmation code rejects result/winner/score/outcome fields, non-ATP rows, starts before the cutoff, observations at or after scheduled start, invalid probabilities and non-finite Profile Gap values.

`market_probability_a`, `core_probability_a`, and `profile_gap` must be produced from the frozen source/model semantics. This runbook does not authorize a new data vendor, a new Core model, a refitted Profile model, or a different quote-selection rule.

## Append a new pre-match batch

Keep the current verified ledger as `prospective_ledger.jsonl` and a new raw batch as `new_batch.jsonl`.

```bash
python -m tennis_genome.experiments.pattern_confirm_ledger \
  --fit research/installment_01/pattern_confirm_001_market_core_fit.json \
  --existing prospective_ledger.jsonl \
  --input new_batch.jsonl \
  --output prospective_ledger.next.jsonl
```

After an external atomic file/version-control operation preserves the prior ledger, promote `prospective_ledger.next.jsonl` to the current ledger. The command re-verifies every old row digest, verifies the frozen fit hash, rejects duplicates across old/new batches, and sorts deterministically by scheduled start then canonical match ID.

Do not append rows after their scheduled start and back-date `observed_at`. The timestamp is evidence about when the prediction inputs existed, not a decorative field.

## Settlement file

Outcomes remain physically separate from the pre-match ledger. Settlement JSONL rows have:

```json
{"match_id":"canonical-id","outcome_a":true,"retirement":false,"walkover":false}
```

For a retirement or walkover, `outcome_a` may be null. Such matches are counted in exclusion accounting and do not enter the confirmatory statistic.

## Evaluate current accumulation

```bash
python -m tennis_genome.experiments.pattern_confirm evaluate \
  --fit research/installment_01/pattern_confirm_001_market_core_fit.json \
  --ledger prospective_ledger.jsonl \
  --outcomes settled_outcomes.jsonl \
  --output pattern_confirm_status.json
```

Evaluation between frozen looks is permitted only as an accrual/status diagnostic. The engine cannot declare confirmation until the exact frozen cumulative look N is present. Do not introduce unscheduled thresholds or select a favorable subset of matches.

Frozen looks:

- `PC-ATP-PG-LOW`: 524, 1,047, 1,570, 2,094 qualifying settled matches.
- `PC-ATP-PG-ABS-HIGH`: 936, 1,872, 2,808, 3,744 qualifying settled matches.

A match can count in both hypotheses if it mechanically satisfies both frozen rules.

## External dependency

The repository now contains the scientific confirmation machinery, but it does not claim a live pre-match feed exists. Future ingestion must obtain, before each target match starts, the frozen market probability plus Core and Profile Gap inputs under the already-defined semantics. If a trustworthy pre-match acquisition path is unavailable for a match, the correct action is to leave that match out of the prospective ledger rather than reconstructing its pre-match row after the fact.

Any new prospective data-source integration must be documented and tested before its rows are allowed into the ledger, without looking at whether those rows would help or hurt the hypotheses.
