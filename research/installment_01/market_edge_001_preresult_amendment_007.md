# MARKET-EDGE-001 — Pre-Result Amendment 007

Status: **FROZEN BEFORE ANY BOOKMAKER-VS-SIGNAL RESULT**

## Trigger

The originally preregistered confirmatory market source was Betfair Historical Data. The project operator is in a jurisdiction where opening/operating the required Betfair account is not a clean operational path. This amendment is therefore a source-access change made for legal/operational reasons, not in response to any MARKET-EDGE result.

No real bookmaker-vs-Profile-Gap or bookmaker-vs-Genome result has been inspected before this amendment.

## Confirmatory market benchmark migration

The primary closing-market information benchmark becomes `BOOKMAKER_CLOSE_V1`, built by `MARKET-BOOK-001` under the following fixed hierarchy:

1. **Valuebetennis closing odds** (`cote1_cloture`, `cote2_cloture`) when both sides are finite decimal odds greater than 1.0.
2. Otherwise **Tennis-Data Pinnacle latest pre-match odds** (`PSW`, `PSL`) when both sides are finite decimal odds greater than 1.0.
3. Otherwise the match has no confirmatory closing-market quote.

When both sources are available, Valuebetennis wins by rule. The source may not be chosen match-by-match based on the resulting probability, signal direction, winner, score, model performance, or any other outcome information.

Opening odds, Bet365 odds, market-average odds, market-maximum odds, and other bookmaker fields are not fallback inputs to the primary confirmatory benchmark. They may only be used in a separately preregistered future diagnostic.

## No-vig transform

For two decimal prices `o_a` and `o_b`, the market probability is fixed to proportional normalization:

```text
q_a = 1 / o_a
q_b = 1 / o_b
p_market_a = q_a / (q_a + q_b)
p_market_b = q_b / (q_a + q_b)
```

This is the repository's existing `proportional_novig_two_way` transform.

## Outcome firewall

Both candidate sources are result-bearing files. `MARKET-BOOK-001` must therefore create a physically separate, outcome-free market artifact before any confirmatory analysis.

### Valuebetennis

The adapter may read only identity/date/tour fields and the two closing-odds fields needed for the market artifact. `vainqueur_id`, `score`, and `duree_min` are forbidden from emitted market records and may not influence source selection, joining, QA, or probability construction.

### Tennis-Data

The raw file labels contestants as `Winner` and `Loser`, so those labels themselves reveal outcome orientation. The adapter must mechanically neutralize every usable row before downstream code sees it:

- normalize both contestant names using the frozen market-name normalizer;
- sort the normalized names lexicographically;
- orient the corresponding `PSW`/`PSL` price to that neutral order;
- discard the Winner/Loser role labels, set scores, result comment, and every other outcome/post-match field from the emitted record.

The neutral order is independent of the winner and signal values.

## Time boundary

The confirmatory development/evaluation population remains capped at **2025-12-31**. Any 2026 bookmaker file or row is rejected from the confirmatory source bundle.

## Coverage gate

`MARKET-BOOK-QA-001` inherits the frozen closing-market coverage requirements, interpreted for a usable two-sided `BOOKMAKER_CLOSE_V1` quote joined to an eligible canonical completed match:

- at least 60% overall coverage per tour;
- at least 50% coverage in every evaluation year 2021-2025;
- at least 100 usable closing quotes in every evaluation year 2021-2025;
- at least 1,000 usable joined prior rows before 2021 per tour;
- all five evaluation years 2021-2025 represented.

QA may use the outcome ledger only to remove walkovers/retirements from the denominator, exactly as the existing market-history QA does. It may not score Profile Gap, Genome, Strict Core, or any market-vs-model outcome.

If the gate fails, the project may acquire more source coverage under the same fixed quote semantics. It may not lower thresholds or change source priority after observing confirmatory results.

## Confirmatory claims unchanged

The four primary claims remain exactly:

1. ATP × Profile Gap;
2. WTA × Profile Gap;
3. ATP × Genome;
4. WTA × Genome.

Unchanged settings include:

- `family_size = 4`;
- family alpha `0.05`;
- conservative planning alpha `0.0125`;
- Holm family-wise correction;
- `min_prior_rows = 1000`;
- strictly earlier-year fitting;
- market recalibration control `alpha + gamma * logit(p_market)`;
- challenger adds only the frozen signal;
- paired proper-score inference and annual/recent stability rules;
- post-2025 prohibition;
- no post-result threshold tuning.

## Scope of claims after migration

`BOOKMAKER_CLOSE_V1` supports the primary **information-overlap** question: does the frozen signal add information beyond a mature pre-match bookmaker market?

It does **not** provide Betfair exchange spread, executable back/lay size, exchange liquidity, commission, or timestamped T-24H/T-6H/T-1H/T-15M checkpoints. Those execution/CLV/economic claims are deferred to a future separately preregistered source that is legally and operationally available to the project.

The existing Betfair implementation remains in the repository for reproducibility and future lawful use; it is not silently reinterpreted as bookmaker data.
