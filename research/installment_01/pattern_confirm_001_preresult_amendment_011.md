# PATTERN-CONFIRM-001 pre-result amendment 011 — provider-derived settlement authority

Status: **REGISTERED AT PROSPECTIVE N=0 BEFORE ANY ELIGIBLE POST-CUTOFF OUTCOME IS INSPECTED**

This amendment repairs settlement provenance only. It does not change either frozen
hypothesis, threshold, correction, sample size, interim look, alpha allocation,
O'Brien-Fleming boundary, provider choice, five-minute timing rule, model coefficient,
or promotion rule.

## Settlement authority

A settlement row may no longer supply `outcome_a`, `retirement`, or `walkover` as
operator assertions. The same Sportradar sport-event payload used for settlement must:

1. reference the prospective record's stable Sportradar event ID;
2. have terminal `sport_event_status.status` equal to `ended` or `closed`;
3. contain `winner_id`;
4. use only the recognized `winning_reason` values `walkover`, `retirement`, or
   `defaulted` when a nonstandard finish is reported; and
5. be captured with an explicit timezone-aware `observed_at`.

During evaluation the provider `winner_id` is resolved against the prospective
record's already-sealed canonical A/B Sportradar competitor IDs. `outcome_a` is then
derived mechanically. Retirement/default/walkover exclusion flags are likewise derived
from the provider winning reason. A winner outside the prospective competitors fails
closed.

The objective is to prevent an operator-supplied result or home/away orientation error
from consuming confirmatory N.
