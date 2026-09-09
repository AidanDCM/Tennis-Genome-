# EXP-001 — Ranking vs Elo

Status: **implementation-ready; real-data run pending source approval/audit**

## Research question

Does a chronologically updated Elo model produce better future pre-match probability estimates than a ranking-only probability model on the same professional singles matches?

This is a baseline experiment. It is not a profitability test.

---

## Null / alternative

**H0:** Elo does not improve out-of-sample probability quality relative to the calibrated ranking baseline.

**H1:** Elo improves future probability quality relative to the calibrated ranking baseline and the improvement is sufficiently stable to justify using Elo as a core baseline.

No minimum improvement is assumed before observing the evidence. Promotion should consider magnitude, uncertainty, stability, and implementation complexity rather than p-values alone.

---

## Population

Initial analysis:
- ATP and WTA should be run separately before any pooled interpretation.
- Completed professional singles matches covered by the audited source.
- Walkovers excluded.
- Primary view excludes retirements.
- Secondary sensitivity view may include retirements and must be labeled separately.
- Ranking model comparisons use only matches where both players have valid pre-match ranks.
- Elo and ranking are scored on the exact same common match IDs.

Do not silently fill missing ranking values for EXP-001.

---

## Data boundary

EXP-001 consumes only canonical:
- `*_pre_match.parquet`
- `*_outcomes.parquet`

The experiment must not read a provider-specific raw CSV/API response directly.

Canonical data must have:
- outcome-independent A/B orientation,
- no outcome columns in pre-match data,
- provenance manifest with source hash and allowed-use status,
- no unresolved critical quality errors.

---

## Ranking baseline

Feature:

`log(rank_B / rank_A)`

A logistic regression calibrates this feature into `P(A wins)`.

For each test year Y:
- fit the ranking calibration using only years `< Y`,
- generate probabilities for Y,
- do not refit using any match from Y before scoring Y.

Later experiments may investigate finer expanding windows, ranking points, inactivity, or alternate rank transforms. Those are not part of EXP-001.

---

## Elo baseline

Current starter Elo has configurable:
- initial rating,
- K factor,
- logistic scale.

The initial implementation is deliberately simple. It is a floor, not the final tennis Elo.

### Same-day rule

If the source has only calendar date and not trustworthy exact start time, all matches on that date use ratings frozen before the date. Daily rating deltas are applied after all predictions for that date.

This deliberately gives up potentially valid same-day information rather than inventing order from CSV layout.

Any future exact-time Elo implementation must be a separately versioned experiment.

---

## Primary metrics

1. Brier score — lower is better.
2. Binary log loss — lower is better.
3. Calibration reliability table / ECE diagnostic.
4. Accuracy — secondary descriptive metric only.

The report currently stores 10-bin expected calibration error (ECE). ECE is bin-dependent and cannot replace the complete reliability analysis.

---

## Stability reporting

Report:
- full common-population metrics,
- year-by-year metrics,
- ATP/WTA separately,
- later: surface/tournament/ranking-band slices after minimum sample rules are implemented.

A headline aggregate improvement that reverses repeatedly by year should not be treated as a stable win.

---

## Required adversarial checks

Before accepting the result:

1. Confirm Player A is not defined by winner/loser source ordering.
2. Confirm no target-match result updates its own pre-match Elo.
3. Confirm same-day CSV order cannot alter predictions under date-only timing.
4. Confirm ranking values are genuinely pre-match/T0-safe under source semantics.
5. Confirm ranking and Elo scores use identical match IDs.
6. Run retirement-excluded and labeled retirement-inclusive sensitivity views.
7. Inspect performance by year for regime dependence.
8. Re-run from the same source snapshot/hash to verify reproducibility.
9. Record chosen Elo hyperparameters and whether they were tuned; if tuned, tuning must be nested inside historical training data.
10. Preserve the final untouched evaluation period once the hyperparameter-search design is added.

---

## Promotion rule

Elo becomes an **A/Core baseline candidate** only if it:
- is leakage-safe,
- is reproducible,
- shows meaningful probability-quality benefit or a compelling complementary role,
- does not rely on one isolated period,
- survives sensitivity/adversarial checks.

A failure is useful. If calibrated ranking is equal or better, record that result and redesign Elo only through registered follow-up hypotheses.

---

## Current implementation entry point

```bash
python -m tennis_genome.experiments.exp001 \
  --pre-match data/processed/atp_pre_match.parquet \
  --outcomes data/processed/atp_outcomes.parquet \
  --min-train-matches 500
```

Run WTA separately with the WTA canonical tables.

The command prints a JSON report with aggregate and yearly comparison metrics.

---

## Not yet claimed

EXP-001 has not yet been run on an approved real historical dataset in this repository. No accuracy, Brier, log-loss, calibration, or betting-performance number should be described as a Tennis Genome result until that run is completed and audited.
